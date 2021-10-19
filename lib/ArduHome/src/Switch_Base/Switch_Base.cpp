#include "Switch_Base.h"

void Switch_Base::set_state_changed_cb(switch_state_changed_cb_t state_changed_cb)
{
    _state_changed_cb = state_changed_cb;
}

void Switch_Base::set_inverted(bool inverted)
{
  _inverted = inverted;
}
