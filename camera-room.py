import datetime
import logging
import os
from os import listdir
from os.path import isfile, join
import pygame
from pynput.keyboard import Key, Listener
from random import choice
from subprocess import call, Popen
import sys
from time import sleep
from picamera import PiCamera, Color


class Config(object):
    pass

class CameraRoom(object):
  def debug(self, msg):
    logging.debug(msg)


  def __init__(self):
    # configuration
    data_dir = '/home/pi/rpi/projects/rpicam/data'
    self.config = Config()
    self.config.video_dir = data_dir + '/test'  # project name
    self.config.clip_length = 10
    self.config.record_countdown = 3
    self.config.replay_count = 3
    self.config.camera_rotation = 180 #  (0, 90, 180, 270)
    self.config.text_size = 40
    self.config.default_fgcolor = 'yellow'
    self.config.default_bgcolor = 'blue'
    self.config.screen_width = 640
    self.config.screen_height = 480
    self.config.background_color_rgb = (0,0,0)
    self.config.text_color_rgb = (255,255,255)


  def display_message(self, message):
    if(not isinstance(message, list)):
      message = [message]
    num_lines = len(message)
    self.display.fill(self.config.background_color_rgb)
    linenum = 0
    for line in message:
      self.debug("DISPLAYING MESSAGE: %s" % line)
      textBitmap = self.font.render(line, True, self.config.text_color_rgb)
      textWidth = textBitmap.get_rect().width
      textHeight = textBitmap.get_rect().height
      full_height = textHeight * num_lines
      x = self.config.screen_width/2 - textWidth/2
      y = self.config.screen_height/2 - full_height/2 + textHeight*linenum
      self.display.blit(textBitmap, [x, y])
      linenum += 1
    pygame.display.flip()


  def record_clip(self):
    self.debug("record_clip()")
    self.camera.annotate_background = Color('green')
    for i in range(self.config.record_countdown,0,-1):
      self.camera.annotate_text = "Recording in %s sec" % i
      sleep(1)
    filename_base = 'video.{:%Y-%m-%d.%H.%M.%S}'.format(datetime.datetime.now())
    raw_filename = self.config.video_dir + '/' + filename_base + '.h264'
    self.camera.start_recording(raw_filename)
    self.camera.annotate_background = None
    self.camera.annotate_foreground = Color('white')
    for i in range(self.config.clip_length,0,-1):
      self.camera.annotate_text = "                            %s" % i
      self.camera.wait_recording(1)
    self.camera.stop_recording()
    # show "converting" message
    self.display_message('Processing video...')
    # convert video file
    final_filename = self.config.video_dir + '/' + filename_base + '.mp4'
    call(["MP4Box", "-fps", "30", "-add", raw_filename, final_filename], stdout=self.devnull, stderr=self.devnull)
    os.remove(raw_filename)
    self.camera.annotate_background = Color('blue')
    # clear message
    self.display_message('')
    return final_filename



  def play_clip(self,filename):
    # play video file
    self.debug("play_clip(%s)" % filename)
    self.subproc = Popen(["omxplayer", filename])
    self.subproc.wait()
    self.subproc = None


  def wait_input(self,timeout_sec):
    self.camera.annotate_text = "Press button to record for 10 sec (enter)"
    start = int(datetime.datetime.now().timestamp())
    wait_time = 0
    key_pressed = False
    self.debug("wait_input(%d)" % timeout_sec)
    while(wait_time < timeout_sec and not key_pressed):
      wait_time = int(datetime.datetime.now().timestamp()) - start
      key_pressed = self.enter_pressed
      sleep(0.1)
    if(key_pressed):
      self.debug("wait_input(%d) - key pressed" % timeout_sec)
      result = True
    else:
      self.debug("wait_input(%d) - timed out" % timeout_sec)
      result = False
    self.camera.annotate_text = ""
    self.enter_pressed = False
    return result


  def on_press(self,key):
    self.debug('{0} pressed'.format(key))

  def on_release(self,key):
    self.debug('{0} release'.format(key))
    terminate_subproc = False
    if key == Key.enter:
      self.debug("enter pressed")
      self.enter_pressed = True
      terminate_subproc = True
    if key == Key.esc or key == Key.space:
      self.debug("esc pressed")
      self.running = False
      terminate_subproc = True
      # Stop listener
      # return False
    if terminate_subproc and self.subproc is not None:
        self.debug("terminating subprocess")
        self.subproc.kill()


  def main(self):
    # init logging
    logging.basicConfig(format='%(asctime)-15s:%(levelname)s:%(filename)s#%(funcName)s(): %(message)s', level=logging.DEBUG, filename='log/camera-room.log')
    self.debug("begin main")
    # init subproc handle
    self.subproc = None
    self.devnull = open(os.devnull,"w")
    # initialize screen display
    pygame.init()
    pygame.mouse.set_visible(False)
    self.font = pygame.font.Font(None, 52)
    self.display = pygame.display.set_mode((self.config.screen_width, self.config.screen_height), pygame.FULLSCREEN)
    self.display_message("initializing camera...")
    # initialize camera
    self.camera = PiCamera(framerate = 30)
    self.camera.rotation = self.config.camera_rotation
    self.camera.annotate_background = Color(self.config.default_bgcolor)
    self.camera.annotate_foreground = Color(self.config.default_fgcolor)
    self.camera.annotate_text_size = self.config.text_size
    # initialize state variables
    last_cr_mode = None
    cr_mode = 'idle'
    self.enter_pressed = False

    # initialize keyboard listener
    listener = Listener(
        on_press=self.on_press,
        on_release=self.on_release)
    listener.start()
  
    self.debug("loading existing clips...")
    # load list of clips from  video_dir + '/*.mp4'
    current_clips = [f for f in listdir(self.config.video_dir) if isfile(join(self.config.video_dir, f))]

    self.running = True
    while self.running:
      # live mode
      while(cr_mode == 'live' and self.running):
        if(last_cr_mode != cr_mode):
          last_cr_mode = cr_mode
          self.debug("entering live mode...")
          # initialize live mode
          # show preview
          self.camera.start_preview()
        # listen for button click
        button = self.wait_input(10)  #TODO: bump up to 60 ?
        if(button):
          #  click button to record five seconds
          clip_filename = self.record_clip()
          # replay the clip, repeat X times (3?)
          self.camera.stop_preview()
          play_count = 0
          cancelled = False
          self.display_message([
            "Clip will play %s times." % self.config.replay_count,
            "Press the button to discard it",
            "or do nothing to keep it."
          ])
          while(play_count < self.config.replay_count and not cancelled):
            cancelled = self.wait_input(2)
            if not cancelled:
              self.play_clip(clip_filename)
              cancelled = self.enter_pressed
              play_count += 1
              if(not cancelled and play_count < self.config.replay_count):
                self.display_message([
                  "Clip will play %s more times." % (self.config.replay_count - play_count),
                  "Press the button to discard it",
                  "or do nothing to keep it."
                ])
          self.display_message('')
          #  click to discard
          button = self.wait_input(1)
          if(button):
            #  click button to discard
            self.debug("discarding clip by user choice")
            self.display_message('discarding clip')
            pass
          else:
            #if kept, add to current_clips
            self.display_message('adding clip to display roll')
            clip_basename = clip_filename[len(self.config.video_dir)+1:]
            current_clips.append(clip_basename)
          self.camera.start_preview()
          self.display_message('')
        else:
          # no user input, return to idle behavior
          cr_mode = 'idle'

      # left live mode, deinitialize
      self.camera.stop_preview()

      while(cr_mode == 'idle' and self.running):
        # idle behavior
        if(last_cr_mode != cr_mode):
          last_cr_mode = cr_mode
          # initialize idle mode
          self.debug("entering idle mode...")
          self.display_message('loading...')
          pass
        # show collected clips in random order
        # get random clip from current_clips
        if(len(current_clips) == 0):
          self.display_message("Press the button to record a video.")
          self.enter_pressed = self.wait_input(5)
        else:
          clip_filename = choice(current_clips)
          self.play_clip(self.config.video_dir + '/' + clip_filename)
        # check for button press, switch to live mode
        if(self.enter_pressed):
          self.debug("enter pressed, leaving idle mode")
          self.enter_pressed = False
          cr_mode = 'live'
      # left idle mode, deinitialize
      pass
    # clean up
    self.camera.stop_preview()



if __name__ == '__main__':
  print("Starting CameraRoom...")
  cr = CameraRoom()
  cr.main()
