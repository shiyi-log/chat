package test

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

var errMediaFixturesUnavailable = errors.New("media fixtures are unavailable")

func resolveMediaFixture(root, name string) (string, error) {
	if root == "" {
		return "", errMediaFixturesUnavailable
	}

	path := filepath.Join(root, name)
	info, err := os.Stat(path)
	if err != nil {
		return "", fmt.Errorf("stat media fixture %q: %w", path, err)
	}
	if !info.Mode().IsRegular() {
		return "", fmt.Errorf("media fixture %q is not a regular file", path)
	}

	return path, nil
}

func mediaFixture(t *testing.T, name string) string {
	t.Helper()

	root, configured := os.LookupEnv("GOFFMPEG_TESTDATA")
	if !configured {
		root = "testdata"
		if _, err := os.Stat(root); errors.Is(err, os.ErrNotExist) {
			t.Skipf("media E2E skipped: fixtures are absent; add %q under testdata/ or set GOFFMPEG_TESTDATA", name)
		} else if err != nil {
			t.Fatalf("inspect default media fixture directory: %v", err)
		}
	} else if root == "" {
		t.Fatal("GOFFMPEG_TESTDATA is set but empty")
	}

	path, err := resolveMediaFixture(root, name)
	if errors.Is(err, errMediaFixturesUnavailable) {
		t.Skipf("media E2E skipped: no fixture root; add %q under testdata/ or set GOFFMPEG_TESTDATA", name)
	}
	if err != nil {
		t.Fatalf("load media fixture %q: %v", name, err)
	}

	return path
}

func requireFFmpegTools(t *testing.T) {
	t.Helper()

	for _, name := range []string{"ffmpeg", "ffprobe"} {
		if _, err := exec.LookPath(name); err != nil {
			t.Skipf("media E2E skipped: required %q executable is not available on PATH: %v", name, err)
		}
	}
}

func TestResolveMediaFixtureUsesConfiguredRoot(t *testing.T) {
	root := t.TempDir()
	fixture := filepath.Join(root, "3gp")
	if err := os.WriteFile(fixture, []byte("fixture"), 0o600); err != nil {
		t.Fatal(err)
	}

	got, err := resolveMediaFixture(root, "3gp")
	if err != nil {
		t.Fatalf("resolveMediaFixture returned error: %v", err)
	}
	if got != fixture {
		t.Fatalf("resolved fixture path = %q, want %q", got, fixture)
	}
}

func TestResolveMediaFixtureReportsMissingFile(t *testing.T) {
	_, err := resolveMediaFixture(t.TempDir(), "missing")
	if !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("resolveMediaFixture error = %v, want os.ErrNotExist", err)
	}
}
