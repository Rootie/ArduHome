#!/usr/bin/env python3

import logging
import sys
import io
import bisect
import re
import os
import shutil
import pathlib
import argparse

from jinja2 import Template

import yaml

import const

_LOGGER = logging.getLogger(__name__)


class CodeInsertions():
    def __init__(self):
        self.Insertions = {}
    
    def add(self, name, code, priority=1000):
        if not name in self.Insertions:
            self.Insertions[name] = []

        insertion = (priority, code)
        index = bisect.bisect(self.Insertions[name], insertion)

        if (not (index > 0 and self.Insertions[name][index-1] == insertion)):
            self.Insertions[name].insert(index, insertion)

    def get(self, name):
        if not name in self.Insertions:
            return None

        return self.Insertions[name]
        

    def replace_insertions(self, code_stream, out_file):
        for line in code_stream:
            if line.startswith('// ArduHome '):
                out_file.write(line.strip())
                out_file.write(' begin\n')
                name = line[12:].strip()
                insertions = self.get(name)
                if insertions != None:
                    for insertion in insertions:
                        self.replace_insertions(io.StringIO(insertion[1]), out_file)
                        out_file.write('\n')
                out_file.write(line.strip())
                out_file.write(' end\n')
            else:
                out_file.write(line)


class CodeGenerator():
    def __init__(self):
        self.code_insertions = CodeInsertions()
        self.ids = {}
        self.named_fragments = {}
    
    def add_named_fragment(self, name, code_fragment):
        self.named_fragments.update({code_fragment: name})
    
    def has_named_fragment(self, code_fragment):
        if code_fragment in self.named_fragments:
            return self.named_fragments[code_fragment]
        else:
            return False

    def get_new_id(self, prefix):
        if not prefix in self.ids:
            self.ids[prefix] = 0
            return prefix
        else:
            self.ids[prefix] += 1
            return '{prefix}_{idx}'.format(prefix=prefix, idx=self.ids[prefix])


    def parse_actions(self, actions_config):
        codes = []
        definitions = ''
        code = ''
        for action_config_container in actions_config:
            action_name, action_config = next(iter(action_config_container.items()))
            if action_name == 'delay':
                #TODO generate variable name
                definitions += 'unsigned long delay_end;'
                delay_ms = re.findall("\d+", action_config)[0]
                code += 'delay_end = millis() + {time};'.format(time=delay_ms)
                codes.append(code)
                code = ''
                code += '''
    if (delay_end < millis())
        break;
    '''
            elif action_name == 'switch.turn_off':
                code += '{id}.set_state(false);'.format(id=action_config)

        codes.append(code)

        if len(codes) > 1:
            class_body = Template('''
    protected:
        {{ definitions }}

        void execute()
        {
            switch (_step)
            {
            case 0:
                break;
            {% for code in codes %}
            case {{ loop.index }}:
                {{ code }}
                next_step();
                break;
            {% endfor %}
            default:
                _step = 0;
                break;
            }
        };
''').render(definitions=definitions, codes=codes)
            class_name = self.has_named_fragment(class_body)
            if class_name == False:
                class_name = self.get_new_id('Automation')
                self.add_named_fragment(class_name, class_body)
                class_definition = Template('''
class {{ class_name }} : public Automation_Base
{
    {{ class_body }}
};
''')
                self.code_insertions.add('Base-Globals', class_definition.render(class_name=class_name, class_body=class_body), 1100)

            instance_name = self.get_new_id('automation')
            self.code_insertions.add('Base-Globals', '{class_name} {instance_name} = {class_name}();'.format(class_name=class_name, instance_name=instance_name), 1101)

            return '{instance_name}.start();'.format(instance_name=instance_name)
        else:
            return codes[0]





class ArduHomeComponent():
    def __init__(self, code_generator: CodeGenerator):
        self.cg = code_generator


class Ethernet(ArduHomeComponent):
    def parse_config(self, config):
        if 'ethernet' not in config:
            return
        
        eth_config = config['ethernet']

        self.cg.code_insertions.add('Base-Includes', '#include <Ethernet.h>')
        self.cg.code_insertions.add('Base-Globals', 'EthernetClient net;')

        ip_str = '{' + ', '.join(eth_config['ip'].split('.')) + '}'

        mac_parts = [ '0x' + part for part in eth_config['mac'].split(':')]
        mac_str = '{' + ', '.join(mac_parts) + '}'
        
        code_begin = '''
byte mac[] = {mac};
byte ip[] = {ip};

Ethernet.begin(mac, ip);
'''

        self.cg.code_insertions.add('Base-Setup', code_begin.format(mac=mac_str, ip=ip_str))


class MQTT(ArduHomeComponent):
    def parse_config(self, config):
        if 'mqtt' not in config:
            return

        mqtt_config = config['mqtt']

        self.cg.code_insertions.add('Base-Includes', '#include <MQTT.h>')
        self.cg.code_insertions.add('Base-Globals', 'MQTTClient client;', 900)

        code_functions = Template('''
void connect() {
  Serial.print("connecting...");
  while (!client.connect("{{ name }}"/*, "try", "try"*/)) {
    Serial.print(".");
    delay(1000);
  }

  Serial.println("\\nconnected!");

  client.publish("home/{{ name }}/arduino/state", String("connected: ") + String(millis()));

// ArduHome MQTT-Connected
}

void messageReceived(String &topic, String &payload) {
  //Serial.println("incoming: " + topic + " - " + payload);
  
// ArduHome MQTT-MessageReceived
}
''')

        self.cg.code_insertions.add('Base-Globals', code_functions.render(name=config['arduhome']['name']), 2000)
        
   
        code_setup = '''
  client.begin("{broker}", net);
  client.onMessage(messageReceived);

  connect();
'''
        self.cg.code_insertions.add('Base-Setup', code_setup.format(broker=mqtt_config['ip']), 2000)

        code_loop = '''
  client.loop();

  if (!client.connected()) {
    connect();
  }
'''
        self.cg.code_insertions.add('Base-Loop', code_loop)
        
    def handle_binary_sensors(self, config, sensors):
        if len(sensors) >= 1:
            code_functions = Template('''
void binary_sensor_state_changed(BinarySensor_Base *binary_sensor, bool state)
{
    client.publish("home/{{ name }}/" + binary_sensor->get_name(), state ? "ON" : "OFF");
}
''')
            self.cg.code_insertions.add('Base-Globals', code_functions.render(name=config['arduhome']['name']))
        
        for binary_sensor in sensors:
            self.cg.code_insertions.add('Base-Setup',
                                "{id}.set_state_changed_cb(binary_sensor_state_changed);".format(id=binary_sensor['id']), 910)
            self.cg.code_insertions.add('MQTT-Connected',
                                'binary_sensor_state_changed(&{id}, {id}.get_state());'.format(
                                    id=binary_sensor['id']))

    def handle_switches(self, config, switches):
        if len(switches) >= 1:
            code_functions = Template('''
void mqtt_switch_state_changed(Switch_Base *a_switch, bool state)
{
    client.publish("home/{{ name }}/" + a_switch->get_name(), state ? "ON" : "OFF");
}
''')
            self.cg.code_insertions.add('Base-Globals', code_functions.render(name=config['arduhome']['name']))
        
        for switch in switches:
            switch.state_changed_actions.append('mqtt_switch_state_changed(a_switch, state);')
            self.cg.code_insertions.add('MQTT-Connected',
                                'client.subscribe("home/{name}/{id}/set");'.format(
                                    name=config['arduhome']['name'], id=switch.config['id']))
            self.cg.code_insertions.add('MQTT-Connected',
                                'mqtt_switch_state_changed(&{id}, {id}.get_state());'.format(
                                    id=switch.config['id']))
            code_message_received = Template('''
if (topic == "home/{{ name }}/{{ id }}/set")
{
  {{ id }}.set_state(payload == "ON" ? true : false);
  return;
}
''')

            self.cg.code_insertions.add('MQTT-MessageReceived', 
                                code_message_received.render(
                                    name=config['arduhome']['name'], id=switch.config['id']))


class Switch():
    def __init__(self):
        self.state_changed_actions = []
        self.turn_on_actions = []
        self.config = {}


class Switch_GPIO_Component(ArduHomeComponent):
    switches = []

    config_defaults = {
        'inverted': False,
        'restore_mode': 'RESTORE_DEFAULT_OFF'
    }

    def parse_config(self, config):
        if 'switch' not in config:
            return

        for switch in config['switch']:
            if switch['platform'] != 'gpio':
                continue

            switch = {**self.config_defaults, **switch}

            switch_entity = Switch()
            switch_entity.config = switch

            self.switches.append(switch_entity)

            self.cg.code_insertions.add('Base-Includes', '#include <ArduHome.h>')

            self.cg.code_insertions.add('Base-Globals',
                'Switch_GPIO {id} = Switch_GPIO({pin}, "{id}");'.format(
                id=switch['id'], pin=switch['pin']))

            if switch['inverted']:
                self.cg.code_insertions.add('Base-Setup',
                    '{id}.set_inverted(true);'.format(
                    id=switch['id']), 900)
            
            initial_state = switch['restore_mode'] in ['ALWAYS_ON', 'RESTORE_DEFAULT_ON', 'RESTORE_INVERTED_ON']
            self.cg.code_insertions.add('Base-Setup',
                '{id}.set_state({state});'.format(
                id=switch['id'], state='true' if initial_state else 'false'), 900)
            
            if 'on_turn_on' in switch:
                switch_entity.turn_on_actions.append(self.cg.parse_actions(switch['on_turn_on']))
    
    def generate_callbacks(self):
        generated_code_fragments = []
        def code_fragment_exists(new_code):
            for code in generated_code_fragments:
                if new_code == code:
                    return True
            return False

        for switch in self.switches:
            code = ''
            for callback_code  in switch.state_changed_actions:
                code += callback_code
            turn_on_code = ''
            for callback_code  in switch.turn_on_actions:
                code += callback_code
            if turn_on_code != '':
                code += '''
if (state)
{
    {{ code }}
}
'''.render(code=turn_on_code)

            cb_name = self.cg.has_named_fragment(code)
            if cb_name == False:
                cb_name = self.cg.get_new_id('switch_state_changed')
                self.cg.add_named_fragment(cb_name, code)

                code_functions = Template('''
void {{ cb_name }}(Switch_Base *a_switch, bool state)
{
    {{ code }}
}
''')
                self.cg.code_insertions.add('Base-Globals', code_functions.render(code=code, cb_name=cb_name), 1200)

            self.cg.code_insertions.add('Base-Setup',
                                    "{id}.set_state_changed_cb({cb_name});".format(id=switch.config['id'], cb_name=cb_name), 910)
            

class BinarySensor_GPIO(ArduHomeComponent):
    sensors = []

    def parse_config(self, config):
        if 'binary_sensor' not in config:
            return

        for binary_sensor in config['binary_sensor']:
            if binary_sensor['platform'] != 'gpio':
                continue

            if not isinstance(binary_sensor['pin'], dict):
                binary_sensor['pin'] = {
                    'number': binary_sensor['pin']
                }
            
            pin_defaults = {
                'mode': 'INPUT',
                'inverted': False
            }
            binary_sensor['pin'] = {**pin_defaults, **binary_sensor['pin']}

            self.sensors.append(binary_sensor)

            self.cg.code_insertions.add('Base-Includes', '#include <ArduHome.h>')
            self.cg.code_insertions.add('Base-Globals',
                'BinarySensor_GPIO {id} = BinarySensor_GPIO({pin}, "{id}");'.format(
                id=binary_sensor['id'], pin=binary_sensor['pin']['number']))
            
            if binary_sensor['pin']['inverted']:
                self.cg.code_insertions.add('Base-Setup',
                    '{id}.set_inverted(true);'.format(
                    id=binary_sensor['id']), 900)

            if binary_sensor['pin']['mode'] != 'INPUT':
                self.cg.code_insertions.add('Base-Setup',
                    '{id}.set_pinMode({mode});'.format(
                    id=binary_sensor['id'], mode=binary_sensor['pin']['mode']), 900)

            self.cg.code_insertions.add('Base-Loop', '{id}.loop();'.format(id=binary_sensor['id']))




def parse_args(argv):
    options_parser = argparse.ArgumentParser(add_help=False)
    options_parser.add_argument(
        "-v", "--verbose", help="Enable verbose ESPHome logs.", action="store_true"
    )
    options_parser.add_argument(
        "-q", "--quiet", help="Disable all ESPHome logs.", action="store_true"
    )

    parser = argparse.ArgumentParser(
        description=f"ArduHome v{const.__version__}", parents=[options_parser]
    )
    
    subparsers = parser.add_subparsers(
        help="Command to run:", dest="command", metavar="command"
    )
    subparsers.required = True

    parser_compile = subparsers.add_parser(
        "compile", help="Read the configuration and compile a program."
    )
    parser_compile.add_argument(
        "configuration", help="Your YAML configuration file(s).", nargs="*", default=["config.yaml"]
    )
    parser_compile.add_argument(
        "--only-generate",
        help="Only generate source code, do not compile.",
        action="store_true",
    )

    subparsers.add_parser("version", help="Print the ArduHome version and exit.")

    arguments = argv[1:]
    if len(arguments) == 0:
        arguments = ["compile"]

    return parser.parse_args(arguments)

def command_compile(args, config_file):
    cg = CodeGenerator()

    config_path = pathlib.Path(config_file).resolve()

    stream = open(config_path, 'r')
    config = yaml.safe_load(stream)

    eth = Ethernet(cg)
    eth.parse_config(config)

    switch_gpio = Switch_GPIO_Component(cg)
    switch_gpio.parse_config(config)

    binary_sensor_gpio = BinarySensor_GPIO(cg)
    binary_sensor_gpio.parse_config(config)

    mqtt = MQTT(cg)
    mqtt.parse_config(config)
    mqtt.handle_binary_sensors(config, binary_sensor_gpio.sensors)
    mqtt.handle_switches(config, switch_gpio.switches)

    switch_gpio.generate_callbacks()

    out_dir = config_path.parent / config['arduhome']['name']

    try:
        os.mkdir(out_dir)
    except FileExistsError:
        pass
    try:
        os.mkdir(out_dir / 'src')
    except FileExistsError:
        pass

    main_cpp_str = '''\
// ArduHome Base-Includes

// ArduHome Base-Globals

void setup() {
  Serial.begin(115200);

// ArduHome Base-Setup
}

void loop() {
// ArduHome Base-Loop
}
'''
    with open(out_dir / 'src/main.cpp', 'w') as out_file:
        cg.code_insertions.replace_insertions(io.StringIO(main_cpp_str), out_file)
    
    lib_dir = out_dir / 'lib'
    if lib_dir.exists():
        shutil.rmtree(lib_dir)
    shutil.copytree(pathlib.Path(__file__).parent.parent.resolve() / 'lib', lib_dir)

    with open(out_dir / 'platformio.ini', 'w') as platformio_config_file:
        platformio_config = Template('''
[env:{{ id }}]
platform = {{ platform }}
framework = arduino
board = {{ board }}
''')
        platformio_config_file.write(platformio_config.render(
            id=config['arduhome']['name'],
            platform=config['arduhome']['platform'],
            board=config['arduhome']['board'],
            )
        )

def run_arduhome(argv):
    args = parse_args(argv)

    if args.command == "version":
        print(f"Version: {const.__version__}")
        return

    for config_file in args.configuration:
        command_compile(args, config_file)
    
def main():
    try:
        return run_arduhome(sys.argv)
    except KeyboardInterrupt:
        return 1


if __name__ == "__main__":
    sys.exit(main())
         