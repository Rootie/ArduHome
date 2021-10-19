#include "BinarySensor_Base.h"

void BinarySensor_Base::set_state_changed_cb(binary_sensor_state_changed_cb_t state_changed_cb)
{
    _state_changed_cb = state_changed_cb;
}
