package test

import (
	"io"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"

	"github.com/teamgram/teamgram-server/pkg/goffmpeg/transcoder"
)

func TestInputNotFound(t *testing.T) {
	requireFFmpegTools(t)

	inputPath := filepath.Join(t.TempDir(), "missing")
	outputPath := filepath.Join(t.TempDir(), "out.mp4")
	err := new(transcoder.Transcoder).Initialize(inputPath, outputPath)
	require.Error(t, err)
}

func runTranscoding(t *testing.T, fixtureName string, progress bool) {
	t.Helper()

	inputPath := mediaFixture(t, fixtureName)
	requireFFmpegTools(t)
	outputPath := filepath.Join(t.TempDir(), fixtureName+".mp4")

	trans := new(transcoder.Transcoder)
	require.NoError(t, trans.Initialize(inputPath, outputPath))

	done := trans.Run(progress)
	if progress {
		for range trans.Output() {
		}
	}
	require.NoError(t, <-done)

	output, err := os.Stat(outputPath)
	require.NoError(t, err)
	require.Greater(t, output.Size(), int64(0))
}

func TestTranscoding3GP(t *testing.T)  { runTranscoding(t, "3gp", false) }
func TestTranscodingAVI(t *testing.T)  { runTranscoding(t, "avi", false) }
func TestTranscodingFLV(t *testing.T)  { runTranscoding(t, "flv", false) }
func TestTranscodingMKV(t *testing.T)  { runTranscoding(t, "mkv", false) }
func TestTranscodingMOV(t *testing.T)  { runTranscoding(t, "mov", false) }
func TestTranscodingMPEG(t *testing.T) { runTranscoding(t, "mpeg", false) }
func TestTranscodingOGG(t *testing.T)  { runTranscoding(t, "ogg", false) }
func TestTranscodingWAV(t *testing.T)  { runTranscoding(t, "wav", false) }
func TestTranscodingWEBM(t *testing.T) { runTranscoding(t, "webm", false) }
func TestTranscodingWMV(t *testing.T)  { runTranscoding(t, "wmv", false) }

func TestTranscodingProgress(t *testing.T) {
	runTranscoding(t, "avi", true)
}

func TestTranscodePipes(t *testing.T) {
	inputPath := mediaFixture(t, "mkv")
	requireFFmpegTools(t)

	trans := new(transcoder.Transcoder)
	require.NoError(t, trans.InitializeEmptyTranscoder())

	input, err := os.Open(inputPath)
	require.NoError(t, err)
	defer input.Close()

	inputPipe, err := trans.CreateInputPipe()
	require.NoError(t, err)
	outputPipe, err := trans.CreateOutputPipe("mp4")
	require.NoError(t, err)

	writeDone := make(chan error, 1)
	go func() {
		_, copyErr := io.Copy(inputPipe, input)
		closeErr := inputPipe.Close()
		if copyErr == nil {
			copyErr = closeErr
		}
		writeDone <- copyErr
	}()

	type outputResult struct {
		bytes int64
		err   error
	}
	readDone := make(chan outputResult, 1)
	go func() {
		written, copyErr := io.Copy(io.Discard, outputPipe)
		closeErr := outputPipe.Close()
		if copyErr == nil {
			copyErr = closeErr
		}
		readDone <- outputResult{bytes: written, err: copyErr}
	}()

	runErr := <-trans.Run(false)
	if runErr != nil {
		_ = inputPipe.CloseWithError(runErr)
		_ = outputPipe.CloseWithError(runErr)
	}
	writeErr := <-writeDone
	output := <-readDone

	require.NoError(t, runErr)
	require.NoError(t, writeErr)
	require.NoError(t, output.err)
	require.Greater(t, output.bytes, int64(0))
}
