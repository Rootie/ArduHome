#include "Switch_GPIO.h"

#include <Arduino.h>


Switch_GPIO::Switch_GPIO(int pin, String name)
{
  _pin = pin;
  _name = name;

  pinMode(pin, OUTPUT);
}

void Switch_GPIO::set_state(bool val)
{
  digitalWrite(_pin, val != _inverted ? HIGH : LOW );

  if (_state_changed_cb != nullptr)
  {
    _state_changed_cb(this, val);
  }
}

bool Switch_GPIO::get_state()
{
  return digitalRead(_pin);
}
