#camera-config.py
import logging
from os.path import isfile
import yaml
from picamera import PiCamera, Color
from picamera.color import NAMED_COLORS
from pynput.keyboard import Key, Listener
import sys
from time import sleep
import select

#interactive adjustment of several app variables:
#- screen/camera resolution
#- brightness

config_filename = 'camera-room.config.yml'

class CameraRoomConfig(object):

  def sort_keys(default, values):
    lt = []
    gt = []
    # sort values
    values.sort()
    for value in values:
      if value < default:
        lt.append(value)
      elif(value > default):
        gt.append(value)
      # value == default will be removed implicitly
    # combine sorted values
    return [default] + gt + lt

  # default is first value in options
  config_options = {
    'resolution' : [
      (640, 480),
      (1280, 720),
      (1640, 922)
    ],
    'rotation' : [
      0,
      90,
      180,
      270
    ],
    'annotate_background' : [None] + list(NAMED_COLORS.keys()),
    'annotate_foreground' : ['white'] + list(NAMED_COLORS.keys()),
    'annotate_text_size' : [30] + list(range(6, 160, 11)),
    'brightness' : sort_keys(50, list(range(0, 100, 5))),
    'contrast' : list(range(0, 100, 10)),
    'image_effect' : ['none'] + list(PiCamera.IMAGE_EFFECTS.keys()),
    'awb_mode' : ['auto'] + list(PiCamera.AWB_MODES.keys()),
    'exposure_mode' : ['auto'] + list(PiCamera.EXPOSURE_MODES.keys()),
    'vflip': [False, True],
    'hflip': [False, True],
  }


  def __init__(self, data = {}):
    self.data = data
    for key,options in self.config_options.items():
      if key not in self.data or self.data[key] is None:
        #logging.debug("key is %s, options are: %s" % (key, options))
        logging.debug("no value found for %s, using default of %s" % (key, options[0]))
        self.data[key] = options[0]


  def setCamera(self, camera):
    self.camera = camera


  def apply(self):
    for key in self.config_options.keys():
      if key in self.data:
        value = self.data[key]
        self.set_value(key, value)


  def set_value(self, key, value):
    self.data[key] = value
    logging.debug("Setting camera.%s to %s" % (key, value))
    #TODO: check for specific keys which may need a reset ?
    if(key in ['annotate_background', 'annotate_foreground'] and value is not None):
      value = Color(value)
    setattr(self.camera, key, value)


  def load(self, filename):
    self.data = yaml.load(open(filename), Loader=yaml.FullLoader)


  def save(self, filename):
    stream = open(config_filename, 'w')
    yaml.dump(self.data, stream)


class CameraConfigEditor(object):

  def change_list_value(self, delta):
    name = self.menu_options[self.current_menu_option_idx]
    if name not in self.config_option_names:
      return
    value = self.config.data[name]
    cur_idx = self.config.config_options[name].index(value)
    new_idx = cur_idx + delta
    logging.debug("name=%s, value=%s, cur_idx=%s, new_idx=%s" % (name, value, cur_idx, new_idx))
    if(new_idx < 0): new_idx = len(self.config.config_options[name]) - 1
    if(new_idx >= len(self.config.config_options[name])): new_idx = 0
    new_value = self.config.config_options[name][new_idx]
    logging.debug("name=%s, value=%s, cur_idx=%s, new_idx=%s new_value=%s" % (name, value, cur_idx, new_idx, new_value))
    # find index of value in options
    self.config.set_value(name, new_value)

  #def on_press(self,key):
  #  logging.debug('{0} pressed'.format(key))

  def on_release(self,key):
    logging.debug('{0} release'.format(key))
    # if input is +
    if key == Key.right:
      #   increase current value
      logging.debug("increase current value")
      self.change_list_value(+1)
    # else if input is -
    elif key == Key.left:
      #   decrease current value
      logging.debug("decrease current value")
      self.change_list_value(-1)
    # else if input is down
    elif key == Key.down:
      #   go to next menu option
      logging.debug("next menu")
      self.current_menu_option_idx += 1
      if(self.current_menu_option_idx >= len(self.menu_options)):
        self.current_menu_option_idx = 0
    # else if input is up
    elif key == Key.up:
      #   go to last menu option
      logging.debug("last menu")
      self.current_menu_option_idx -= 1
      if(self.current_menu_option_idx < 0):
        self.current_menu_option_idx = len(self.menu_options)-1
    elif key == Key.enter:
      #   select current (child) option
      name = self.menu_options[self.current_menu_option_idx]
      logging.debug("selecting current menu item: "+name)
      if(name == 'save'):
        self.config.save(config_filename)
        self.camera.annotate_text = 'Saved config to '+config_filename
        sleep(2)
      elif(name == 'quit'):
        self.running = False
    elif key == Key.esc:
      #   select current (child) option
      logging.debug("escape - exit")
      self.running = False


  def __init__(self):
    logging.basicConfig(format='%(asctime)-15s:%(levelname)s:%(filename)s#%(funcName)s(): %(message)s', level=logging.DEBUG)
    print("Starting CameraRoomConfig...")
    # load existing data, if available
    self.config = CameraRoomConfig()
    self.config_option_names = list(self.config.config_options.keys())
    self.menu_options = self.config_option_names + ['save', 'quit']
    self.current_menu_option_idx = 0
    if isfile(config_filename):
      self.config.load(config_filename)
      is_new = False
    else:
      is_new = True
    # initialize keyboard listener
    self.listener = Listener(
        #on_press=on_press,
        on_release=self.on_release)
    self.listener.start()
    # initialize camera
    self.camera = PiCamera(framerate = 30)
    self.config.setCamera(self.camera)
    if not is_new:
      self.config.apply()
    # initialize display
    self.camera.start_preview()

  def main(self):
    try:
      self.running = True
      while self.running:
        # show current menu option
        name = self.menu_options[self.current_menu_option_idx]
        text = name
        if name in self.config_option_names:
          text += (": %s" % str(self.config.data[name]))
        self.camera.annotate_text = text
        # listen for input events
        sleep(0.1)
    except:
      # catch exceptions to ensure correct shutdown
      pass
    # shutdown
    logging.debug("shutting down")
    self.listener.stop()
    self.camera.stop_preview()
    # clear keyboard buffer
    cleared = False
    while not cleared:
      if select.select([sys.stdin,],[],[],0.0)[0]: r = sys.stdin.read(1)
      else: cleared = True


if __name__ == '__main__':
  editor = CameraConfigEditor()
  editor.main()

  