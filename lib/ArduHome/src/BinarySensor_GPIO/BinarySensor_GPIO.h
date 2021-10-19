#ifndef BINARYSENSOR_GPIO_H
#define BINARYSENSOR_GPIO_H

// Include the Bounce2 library found here :
// https://github.com/thomasfredericks/Bounce2
#include <Bounce2.h>

#include "../BinarySensor_Base/BinarySensor_Base.h"

class BinarySensor_GPIO : public BinarySensor_Base {
 public:
  BinarySensor_GPIO(int pin, String name);
  void set_inverted(bool inverted);
  void set_pinMode(int mode);
  void loop();
  bool get_state();
 private:
  int _pin;
  bool _inverted = false;
  Bounce _bounce;
};

#endif // BINARYSENSOR_GPIO_H
