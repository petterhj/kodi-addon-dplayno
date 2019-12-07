# Imports
import os
import re
import sys
import time
import logging
import pexpect
import pexpect.popen_spawn
from urllib import unquote
from distutils.spawn import find_executable


# Logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('[Dplay.%s]' % (__name__))


# Class: DplayDownloadTask
class DplayDownloadTask(object):
    # Init
    def __init__(self, stream_url, video_id, video_full_name, duration, output_path):
        logger.info('Initializing new download task')

        # Properties
        self.stream_url = unquote(stream_url)
        self.video_id = int(video_id)
        self.video_full_name = video_full_name
        self.duration = int(duration)
        self.output_path = output_path
        
        logger.debug('Stream URL: %s' % (self.stream_url))
        logger.debug('Video ID: %d' % (self.video_id))
        logger.debug('Full name: %s' % (self.video_full_name))
        logger.debug('Duration: %d' % (self.duration))
        logger.debug('Output path: %s' % (self.output_path))
        
        # Task
        self.command = None
        self.destination = None
        self.process = None
        self._prepare_task()

        logger.debug('Command: %s' % (self.command))
        logger.debug('Destination: %s' % (self.destination))


    # Start
    def start(self, progress_callback=None):
        logger.info('Starting download of video id %d (duration = %d ms)' % (
            self.video_id, self.duration
        ))

        progress_callback = progress_callback or self._progress_callback

        # Execute
        return self._execute(progress_callback)

    
    # Abort
    def abort(self):
        logger.warning('Cancelling download task')
        # print '-'*500
        # self.process.kill(pexpect.signal.SIGINT)


    # Prepare
    def _prepare_task(self):
        logger.info('Preparing download task (doing checks)')

        # Checks
        checks = [
            self.stream_url is not None,
            self.video_id is not None,
            self.duration is not None,
            self.duration > 0,
            find_executable('ffmpeg') is not None,
            os.path.exists(self.output_path),
        ]

        if not all(checks):
            logger.error('Checks failed (%s)' % (str(checks)))
            raise Exception('checks failed')

        # Output destination
        # timestamp = int(time.time())
        # output_file = 'videoid%d_%s.mp4' % (self.video_id, str(timestamp))
        output_file = ''.join([c for c in self.video_full_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        output_file = output_file.replace(' ', '_').replace('__', '_').lower()
        self.destination = os.path.join(self.output_path, output_file + '.mp4')
        
        # Command
        self.command = 'ffmpeg.exe -i %s -c copy -bsf:a aac_adtstoasc %s' % (
            self.stream_url, self.destination
        )

    
    # Execute
    def _execute(self, progress_callback):
        logger.info('Spawning ffmpeg process, cmd=%s' % (self.command))

        self.process = pexpect.popen_spawn.PopenSpawn(self.command)

        progress_callback(0)

        while True:
            expectations = ['\n', 'already exists']
            
            try:
                expected = self.process.expect(expectations)

                if expected == 0:
                    progress = self._frame_received(self.process.before)
                    
                    if progress >= 0 and progress <= 100:
                        progress_callback(progress)
                
                elif expected == 1:
                    logger.error('File already exists')
                    raise Exception('file already exists')
                
            except pexpect.EOF:
                logger.info('ffmpeg process ended')
                break

            # except Exception as e:
            #     logger.error('ffmpeg process failed, %s' % (str(e)))
            #     raise Exception('ffmpeg failed')

        return True


    # Frame received
    def _frame_received(self, line):
        # Parse frame
        raw_update = {}
        
        for match in re.finditer(r'(?P<key>\S+)=\s*(?P<value>\S+)', line.decode()):
            raw_update[match.group('key')] = match.group('value')

        if not raw_update or not raw_update.get('time'):
            return
        
        time = self._parse_timecode(raw_update.get('time'))

        if not time:
            return

        # Determine progress
        progress = int(((time / self.duration) * 100))

        logger.info('%s = %s %%' % (
            ', '.join(['%s=%s' % (k, v) for k, v in raw_update.iteritems()]),
            str(progress)
        ))

        return progress

    
    # Parse timecode
    def _parse_timecode(self, time_code):
        time_units_match = re.match(
            r"(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+.\d+)", time_code)
        if time_units_match is not None:
            return ((int(time_units_match.group("hours")) * 3600 + int(
                time_units_match.group("minutes")) * 60 + float(time_units_match.group("seconds"))) * 1000)
        return None

    
    # Progress callback
    def _progress_callback(self, progress):
        pass


# Main
if __name__ == '__main__':
    # stream_url = 'http://multiplatform-f.akamaihd.net/i/multi/will/bunny/big_buck_bunny_,640x360_400,640x360_700,640x360_1000,950x540_1500,.f4v.csmil/master.m3u8'
    # duration = 596490

    '''
    1: stream url (quoted)
    2: video id
    3: video full name
    4: video duration (ms)
    5: download path
    '''

    # Dialogs
    import xbmcgui
    
    ndlg = xbmcgui.Dialog()
    # pdlg = xbmcgui.DialogProgress()
    pdlg = xbmcgui.DialogProgressBG()

    # Task
    try:
        task = DplayDownloadTask(*sys.argv[1:6])

        # Progress callback
        # pdlg.create('Dplay Download', 'Video: %s' % (task.video_full_name), 'Starting...')
        pdlg.create('Dplay', 'Downloading "%s"' % (task.video_full_name))

        def callback(progress):
            # if pdlg.iscanceled():
            #     task.abort()
            #     pdlg.close()

            # pdlg.update(*[
            #     progress, 
            #     'Video: %s' % (task.video_full_name),
            #     'Progress: %d %%' % (progress),
            # ])
            pdlg.update(percent=progress)

        # Start
        done = task.start(progress_callback=callback)

    except Exception as e:
        pdlg.close()
        logger.error('Download failed, error=%s' % (str(e)))
        ndlg.notification('Dplay', 'Download failed (%s)' % (str(e)))

    else:
        pdlg.close()
        ndlg.notification('Dplay', '%s' % (
            'Done downloading' if done else 'Download failed'
        ))