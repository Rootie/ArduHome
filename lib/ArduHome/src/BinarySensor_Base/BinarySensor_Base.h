#ifndef BINARYSENSOR_BASE_h
#define BINARYSENSOR_BASE_h

#include "Arduino.h"

#include "../Common/Nameable.h"

class BinarySensor_Base;


typedef void (*binary_sensor_state_changed_cb_t)(BinarySensor_Base *binary_sensor, bool state);


class BinarySensor_Base : public Nameable
{
  public:
    virtual void loop() = 0;
    virtual bool get_state() = 0;
    void set_state_changed_cb(binary_sensor_state_changed_cb_t state_changed_cb);
  protected:
    binary_sensor_state_changed_cb_t _state_changed_cb = nullptr;
};

#endif
