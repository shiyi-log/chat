package jpeg

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

var errJPEGFixturesUnavailable = errors.New("JPEG fixtures are unavailable")

func resolveJPEGFixture(root, name string) (string, error) {
	if root == "" {
		return "", errJPEGFixturesUnavailable
	}

	path := filepath.Join(root, name)
	info, err := os.Stat(path)
	if err != nil {
		return "", fmt.Errorf("stat JPEG fixture %q: %w", path, err)
	}
	if !info.Mode().IsRegular() {
		return "", fmt.Errorf("JPEG fixture %q is not a regular file", path)
	}

	return path, nil
}

func jpegFixturePath(t testing.TB, name string) string {
	t.Helper()

	root, configured := os.LookupEnv("JPEG_TESTDATA")
	if configured {
		if root == "" {
			t.Fatal("JPEG_TESTDATA is set but empty")
		}
		path, err := resolveJPEGFixture(root, name)
		if err != nil {
			t.Fatalf("load configured JPEG fixture %q: %v", name, err)
		}
		return path
	}

	roots := []string{
		filepath.Join("..", "testdata"),
		filepath.Join(runtime.GOROOT(), "src", "image", "testdata"),
	}
	for _, candidate := range roots {
		info, err := os.Stat(candidate)
		if errors.Is(err, os.ErrNotExist) {
			continue
		}
		if err != nil {
			t.Fatalf("inspect JPEG fixture directory %q: %v", candidate, err)
		}
		if !info.IsDir() {
			continue
		}

		path, err := resolveJPEGFixture(candidate, name)
		if err == nil {
			return path
		}
		if !errors.Is(err, os.ErrNotExist) {
			t.Fatalf("load JPEG fixture %q from %q: %v", name, candidate, err)
		}
	}

	t.Skipf("JPEG test skipped: fixture %q is missing; set JPEG_TESTDATA to the Go image testdata directory", name)
	return ""
}

func TestResolveJPEGFixtureUsesConfiguredRoot(t *testing.T) {
	root := t.TempDir()
	fixture := filepath.Join(root, "video-001.jpeg")
	if err := os.WriteFile(fixture, []byte("fixture"), 0o600); err != nil {
		t.Fatal(err)
	}

	got, err := resolveJPEGFixture(root, "video-001.jpeg")
	if err != nil {
		t.Fatalf("resolveJPEGFixture returned error: %v", err)
	}
	if got != fixture {
		t.Fatalf("resolved fixture path = %q, want %q", got, fixture)
	}
}

func TestResolveJPEGFixtureReportsMissingFile(t *testing.T) {
	_, err := resolveJPEGFixture(t.TempDir(), "missing.jpeg")
	if !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("resolveJPEGFixture error = %v, want os.ErrNotExist", err)
	}
}
