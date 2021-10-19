#ifndef SWITCH_GPIO_h
#define SWITCH_GPIO_h

#include "../Switch_Base/Switch_Base.h"

class Switch_GPIO : public Switch_Base
{
  public:
    Switch_GPIO(int pin, String name);
    void set_state(bool val);
    bool get_state();
  private:
    int _pin;
};

#endif
