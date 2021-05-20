from pygame import mixer
import time
  
# Starting the mixer
mixer.init()
  
# Loading the song
mixer.music.load("happy (because I'm happy).mp3")
  
# Setting the volume
mixer.music.set_volume(0.2)
  
# Start playing the song
mixer.music.play()

while True:
    time.sleep(5)
    mixer.music.pause()
    time.sleep(5)
    mixer.music.unpause()

# dif conditions 
if "happy":
    mixer.music.load("happy (because I'm happy).mp3")
  
if "sad":
    mixer.music.load("sad (say something).mp3")


# infinite loop
# while True:
      
#     print("Press 'p' to pause, 'r' to resume")
#     print("Press 'e' to exit the program")
#     query = input("  ")
      
#     if query == 'p':
  
#         # Pausing the music
#         mixer.music.pause()     
#     elif query == 'r':
  
#         # Resuming the music
#         mixer.music.unpause()
#     elif query == 'e':
  
#         # Stop the mixer
#         mixer.music.stop()
#         break

