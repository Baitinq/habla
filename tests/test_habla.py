import unittest
from unittest import mock

import sounddevice as sd

from habla.habla import Recorder


class RecorderTest(unittest.TestCase):
    @mock.patch("habla.habla.sd.check_input_settings")
    def test_failed_stream_creation_does_not_mark_recorder_as_recording(self, _):
        recorder = Recorder()

        with mock.patch(
            "habla.habla.sd.InputStream",
            side_effect=sd.PortAudioError("failed to open input"),
        ):
            with self.assertRaises(sd.PortAudioError):
                recorder.start(streaming_conn=mock.sentinel.connection)

        self.assertFalse(recorder.recording)
        self.assertIsNone(recorder.stream)
        self.assertIsNone(recorder.streaming_conn)

    @mock.patch("habla.habla.sd.check_input_settings")
    def test_failed_stream_start_closes_stream(self, _):
        recorder = Recorder()
        stream = mock.Mock()
        stream.start.side_effect = sd.PortAudioError("failed to start input")

        with mock.patch("habla.habla.sd.InputStream", return_value=stream):
            with self.assertRaises(sd.PortAudioError):
                recorder.start(streaming_conn=mock.sentinel.connection)

        stream.close.assert_called_once_with()
        self.assertFalse(recorder.recording)
        self.assertIsNone(recorder.stream)
        self.assertIsNone(recorder.streaming_conn)


if __name__ == "__main__":
    unittest.main()
