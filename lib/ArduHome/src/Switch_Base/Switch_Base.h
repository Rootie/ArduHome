#ifndef SWITCH_BASE_h
#define SWITCH_BASE_h

#include "Arduino.h"

#include "../Common/Nameable.h"

class Switch_Base;


typedef void (*switch_state_changed_cb_t)(Switch_Base *a_switch, bool state);


class Switch_Base : public Nameable
{
  public:
    void set_inverted(bool inverted);
    virtual void set_state(bool val) = 0;
    virtual bool get_state() = 0;
    void set_state_changed_cb(switch_state_changed_cb_t state_changed_cb);
  protected:
    bool _inverted = false;
    switch_state_changed_cb_t _state_changed_cb = nullptr;
};

#endif
