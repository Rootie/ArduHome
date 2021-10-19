#ifndef NAMEABLE_h
#define NAMEABLE_h

#include "Arduino.h"

class Nameable
{
  public:
    String get_name();
  protected:
    String _name;
};

#endif
