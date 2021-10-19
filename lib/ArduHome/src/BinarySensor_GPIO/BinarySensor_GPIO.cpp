#include "BinarySensor_GPIO.h"

BinarySensor_GPIO::BinarySensor_GPIO(int pin, String name)
{
  _pin = pin;
  _name = name;

  _bounce = Bounce();
  _bounce.attach(pin, INPUT);
}

void BinarySensor_GPIO::set_inverted(bool inverted)
{
  _inverted = inverted;
}

void BinarySensor_GPIO::set_pinMode(int mode)
{
  _bounce.attach(_pin, mode);
}

void BinarySensor_GPIO::loop()
{
  if (_bounce.update())
  {
    if (_state_changed_cb != nullptr)
    {
      _state_changed_cb(this, _bounce.read() != _inverted);
    }
  }
}

bool BinarySensor_GPIO::get_state()
{
  return _bounce.read();
}
