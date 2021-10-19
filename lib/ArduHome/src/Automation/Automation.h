#ifndef AUTOMATION_H
#define AUTOMATION_H

#include "Arduino.h"

class Automation_Base
{
  public:
    void start() { _step = 1; update();};
    void update() { execute(); };
  protected:
    void next_step() { _step++; update(); };
    virtual void execute() = 0;
    unsigned int _step = 0;
};

#endif
