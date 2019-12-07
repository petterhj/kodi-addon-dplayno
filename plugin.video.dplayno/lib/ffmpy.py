import errno
import shlex
import subprocess
import os
import re

__version__ = '0.2.2'

class FFtool(object):
    def __init__(self, executable, global_options=None, inputs=None, outputs=None):
        self.executable = executable
        self._cmd = [executable]

        global_options = global_options or []
        if _is_sequence(global_options):
            normalized_global_options = []
            for opt in global_options:
                normalized_global_options += shlex.split(opt)
        else:
            normalized_global_options = shlex.split(global_options)

        self._cmd += normalized_global_options
        self._cmd += _merge_args_opts(inputs, add_input_option=True)
        self._cmd += _merge_args_opts(outputs)

        self.cmd = subprocess.list2cmdline(self._cmd)
        self.process = None

    def __repr__(self):
        return '<{0!r} {1!r}>'.format(self.__class__.__name__, self.cmd)

    def start(self, input_data=None, stdin=None, stdout=None, stderr=None):
        if input_data is not None or stdin is None:
            stdin = subprocess.PIPE

        try:
            self.process = subprocess.Popen(
                self._cmd,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr
            )
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise FFExecutableNotFoundError(
                    "Executable '{0}' not found".format(self.executable))
            else:
                raise

class FFmpeg(FFtool):
    """Wrapper for various `FFmpeg <https://www.ffmpeg.org/>`_ related applications (ffmpeg,
    ffprobe).
    """

    def __init__(self, executable='ffmpeg', global_options=None, inputs=None, outputs=None,
                 update_size=2048):
        """Initialize FFmpeg command line wrapper.

        Compiles FFmpeg command line from passed arguments (executable path, options, inputs and
        outputs). ``inputs`` and ``outputs`` are dictionares containing inputs/outputs as keys and
        their respective options as values. One dictionary value (set of options) must be either a
        single space separated string, or a list or strings without spaces (i.e. each part of the
        option is a separate item of the list, the result of calling ``split()`` on the options
        string). If the value is a list, it cannot be mixed, i.e. cannot contain items with spaces.
        An exception are complex FFmpeg command lines that contain quotes: the quoted part must be
        one string, even if it contains spaces (see *Examples* for more info).
        For more info about FFmpeg command line format see `here
        <https://ffmpeg.org/ffmpeg.html#Synopsis>`_.

        :param str executable: path to ffmpeg executable; by default the ``ffmpeg`` command will be
            searched for in the ``PATH``, but can be overridden with an absolute path to ``ffmpeg``
            executable
        :param iterable global_options: global options passed to ``ffmpeg`` executable (e.g.
            ``-y``, ``-v`` etc.); can be specified either as a list/tuple/set of strings, or one
            space-separated string; by default no global options are passed
        :param dict inputs: a dictionary specifying one or more input arguments as keys with their
            corresponding options (either as a list of strings or a single space separated string) as
            values
        :param dict outputs: a dictionary specifying one or more output arguments as keys with their
            corresponding options (either as a list of strings or a single space separated string) as
            values
        """
        super(FFmpeg, self).__init__(executable, global_options, inputs, outputs)
        self.update_size = update_size

    def run(self, input_data=None, stdin=None, stdout=None, on_progress=None):
        """Execute FFmpeg command line.

        ``input_data`` can contain input for FFmpeg in case ``pipe`` protocol is used for input.
        ``stdout`` and ``stderr`` specify where to redirect the ``stdout`` and ``stderr`` of the
        process. By default no redirection is done, which means all output goes to running shell
        (this mode should normally only be used for debugging purposes). If FFmpeg ``pipe`` protocol
        is used for output, ``stdout`` must be redirected to a pipe by passing `subprocess.PIPE` as
        ``stdout`` argument.

        Returns a 2-tuple containing ``stdout`` and ``stderr`` of the process. If there was no
        redirection or if the output was redirected to e.g. `os.devnull`, the value returned will
        be a tuple of two `None` values, otherwise it will contain the actual ``stdout`` and
        ``stderr`` data returned by ffmpeg process.

        More info about ``pipe`` protocol `here <https://ffmpeg.org/ffmpeg-protocols.html#pipe>`_.

        :param str input_data: input data for FFmpeg to deal with (audio, video etc.) as bytes (e.g.
            the result of reading a file in binary mode)
        :param stdin: replace FFmpeg ``stdin`` (default is `None` which means `subprocess.PIPE`)
        :param stdout: redirect FFmpeg ``stdout`` there (default is `None` which means no
            redirection)
        :return: a 2-tuple containing ``stdout`` and ``stderr`` of the process
        :rtype: tuple
        :raise: `FFRuntimeError` in case FFmpeg command exits with a non-zero code;
            `FFExecutableNotFoundError` in case the executable path passed was not valid
        """
        self.start(input_data, stdin, stdout, subprocess.PIPE)
        return [None, self.wait(on_progress)]

    def wait(self, on_progress=None, stderr_ring_size=30):
        stderr_ring = []
        is_running = True
        stderr_fileno = self.process.stderr.fileno()
        ff_state = FFstate()
        while is_running:
            latest_update = os.read(stderr_fileno, self.update_size)
            if ff_state.consume(latest_update) and on_progress is not None:
                on_progress(ff_state)
            stderr_ring.append(latest_update.decode())
            if len(stderr_ring) > stderr_ring_size:
                del stderr_ring[0]
            is_running = self.process.poll() is None

        stderr_out = str.join("", stderr_ring)
        if self.process.returncode != 0:
            raise FFRuntimeError(self.cmd, self.process.returncode, stderr_out)

        return stderr_out


class FFstate:
    def __init__(self):
        self.frame = None
        self.fps = None
        self.size = None
        self.time = None

    def consume(self, update):
        raw_update_dict = {}
        for match in re.finditer(r"(?P<key>\S+)=\s*(?P<value>\S+)", update.decode()):
            raw_update_dict[match.group("key")] = match.group("value")
        updated = self.update_frame(raw_update_dict.get("frame")) + \
            self.update_fps(raw_update_dict.get("fps")) + \
            self.update_size(raw_update_dict.get("size") or raw_update_dict.get("Lsize", "")) + \
            self.update_time(raw_update_dict.get("time", ""))
        return updated > 0

    def update_frame(self, raw_frame):
        if raw_frame is not None:
            self.frame = int(raw_frame)
            return True
        return False

    def update_fps(self, fps_raw):
        if fps_raw is not None:
            self.fps = float(fps_raw)
            return True
        return False

    def update_size(self, raw_size):
        digits_match = re.match(r"(?P<size_in_kb>\d+)kB", raw_size)
        if digits_match is not None:
            self.size = int(digits_match.group("size_in_kb")) * 1000
            return True
        return False

    def update_time(self, raw_time):
        time_units_match = re.match(
            r"(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+.\d+)", raw_time)
        if time_units_match is not None:
            self.time = int(time_units_match.group("hours")) * 3600 + int(
                time_units_match.group("minutes")) * 60 + float(time_units_match.group("seconds"))
            return True
        return False


class FFprobe(FFtool):
    """Wrapper for `ffprobe <https://www.ffmpeg.org/ffprobe.html>`_."""

    def __init__(self, executable='ffprobe', global_options='', inputs=None):
        """Create an instance of FFprobe.

        Compiles FFprobe command line from passed arguments (executable path, options, inputs).
        FFprobe executable by default is taken from ``PATH`` but can be overridden with an
        absolute path. For more info about FFprobe command line format see
        `here <https://ffmpeg.org/ffprobe.html#Synopsis>`_.

        :param str executable: absolute path to ffprobe executable
        :param iterable global_options: global options passed to ffmpeg executable; can be specified
            either as a list/tuple of strings or a space-separated string
        :param dict inputs: a dictionary specifying one or more inputs as keys with their
            corresponding options as values
        """
        super(FFprobe, self).__init__(
            executable=executable,
            global_options=global_options,
            inputs=inputs
        )

    def run(self, stdout=subprocess.PIPE, stderr=subprocess.PIPE):
        self.start(stdout=stdout, stderr=stderr)
        out = self.process.communicate()
        if self.process.returncode != 0:
            raise FFRuntimeError(self.cmd, self.process.returncode, out[1])
        return out

class FFExecutableNotFoundError(Exception):
    """Raise when FFmpeg/FFprobe executable was not found."""


class FFRuntimeError(Exception):
    """Raise when FFmpeg/FFprobe command line execution returns a non-zero exit code.

    The resulting exception object will contain the attributes relates to command line execution:
    ``cmd``, ``exit_code``, ``stdout``, ``stderr``.
    """

    def __init__(self, cmd, exit_code, stderr):
        self.cmd = cmd
        self.exit_code = exit_code
        self.stderr = stderr

        message = "`{0}` exited with status {1}\n\n\nSTDERR:\n{2}".format(
            self.cmd,
            exit_code,
            (stderr or b'').decode()
        )

        super(FFRuntimeError, self).__init__(message)


def _is_sequence(obj):
    """Check if the object is a sequence (list, tuple etc.).

    :param object obj: an object to be checked
    :return: True if the object is iterable but is not a string, False otherwise
    :rtype: bool
    """
    return hasattr(obj, '__iter__') and not isinstance(obj, str)


def _merge_args_opts(args_opts_dict, **kwargs):
    """Merge options with their corresponding arguments.

    Iterates over the dictionary holding arguments (keys) and options (values). Merges each
    options string with its corresponding argument.

    :param dict args_opts_dict: a dictionary of arguments and options
    :param dict kwargs: *input_option* - if specified prepends ``-i`` to input argument
    :return: merged list of strings with arguments and their corresponding options
    :rtype: list
    """
    merged = []

    if not args_opts_dict:
        return merged

    for arg, opt in args_opts_dict.items():
        if not _is_sequence(opt):
            opt = shlex.split(opt or '')
        merged += opt

        if not arg:
            continue

        if 'add_input_option' in kwargs:
            merged.append('-i')

        merged.append(arg)

    return merged