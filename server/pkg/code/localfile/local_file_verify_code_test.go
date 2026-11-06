package localfile

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/teamgram/proto/mtproto"
	"github.com/teamgram/teamgram-server/pkg/code/conf"
)

func TestLocalFileVerifierWritesPrivateCodeAndConsumesItOnce(t *testing.T) {
	outbox := filepath.Join(t.TempDir(), "outbox")
	verifier := New(&conf.SmsVerifyCodeConfig{LocalOutboxDir: outbox})

	extraData, err := verifier.SendSmsVerifyCode(context.Background(), "+15551234567", "73104", "code-hash")
	if err != nil {
		t.Fatalf("send local code: %v", err)
	}
	if extraData != "73104" {
		t.Fatalf("expected verification data to retain the generated code, got %q", extraData)
	}

	entries, err := os.ReadDir(outbox)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 {
		t.Fatalf("expected one outbox entry, got %d", len(entries))
	}
	entryPath := filepath.Join(outbox, entries[0].Name())
	info, err := os.Stat(entryPath)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("expected private OTP file permissions 0600, got %04o", info.Mode().Perm())
	}
	dirInfo, err := os.Stat(outbox)
	if err != nil {
		t.Fatal(err)
	}
	if dirInfo.Mode().Perm() != 0o700 {
		t.Fatalf("expected private outbox directory permissions 0700, got %04o", dirInfo.Mode().Perm())
	}

	var message struct {
		PhoneNumber string `json:"phone_number"`
		PhoneCode   string `json:"phone_code"`
		CodeHash    string `json:"phone_code_hash"`
	}
	data, err := os.ReadFile(entryPath)
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(data, &message); err != nil {
		t.Fatalf("decode outbox entry: %v", err)
	}
	if message.PhoneNumber != "+15551234567" || message.PhoneCode != "73104" || message.CodeHash != "code-hash" {
		t.Fatalf("unexpected local code message: %#v", message)
	}

	if err := verifier.VerifySmsCode(context.Background(), "code-hash", "00000", extraData); err != mtproto.ErrPhoneCodeInvalid {
		t.Fatalf("expected wrong code to be rejected, got %v", err)
	}
	if err := verifier.VerifySmsCode(context.Background(), "code-hash", "73104", extraData); err != nil {
		t.Fatalf("verify generated code: %v", err)
	}
	if _, err := os.Stat(entryPath); !os.IsNotExist(err) {
		t.Fatalf("expected successful verification to consume the outbox entry, stat error: %v", err)
	}
	if err := verifier.VerifySmsCode(context.Background(), "code-hash", "73104", extraData); err != mtproto.ErrPhoneCodeInvalid {
		t.Fatalf("expected consumed code to be rejected, got %v", err)
	}
}

func TestLocalFileVerifierConsumesCodeOnlyOnceConcurrently(t *testing.T) {
	verifier := New(&conf.SmsVerifyCodeConfig{LocalOutboxDir: filepath.Join(t.TempDir(), "outbox")})
	extraData, err := verifier.SendSmsVerifyCode(context.Background(), "+15551234567", "73104", "code-hash")
	if err != nil {
		t.Fatal(err)
	}

	results := make(chan error, 2)
	var group sync.WaitGroup
	for range 2 {
		group.Add(1)
		go func() {
			defer group.Done()
			results <- verifier.VerifySmsCode(context.Background(), "code-hash", "73104", extraData)
		}()
	}
	group.Wait()
	close(results)

	successes := 0
	invalid := 0
	for err := range results {
		switch err {
		case nil:
			successes++
		case mtproto.ErrPhoneCodeInvalid:
			invalid++
		default:
			t.Fatalf("unexpected verification result: %v", err)
		}
	}
	if successes != 1 || invalid != 1 {
		t.Fatalf("expected one success and one invalid result, got %d success and %d invalid", successes, invalid)
	}
}

func TestLocalFileVerifierRemovesExpiredMessageOnAttempt(t *testing.T) {
	outbox := filepath.Join(t.TempDir(), "outbox")
	verifier := New(&conf.SmsVerifyCodeConfig{LocalOutboxDir: outbox})
	extraData, err := verifier.SendSmsVerifyCode(context.Background(), "+15551234567", "73104", "code-hash")
	if err != nil {
		t.Fatalf("send local code: %v", err)
	}

	entries, err := os.ReadDir(outbox)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 {
		t.Fatalf("expected one outbox entry, got %d", len(entries))
	}
	entryPath := filepath.Join(outbox, entries[0].Name())
	message := outboxMessage{
		PhoneNumber: "+15551234567",
		PhoneCode:   "73104",
		CodeHash:    "code-hash",
		ExpiresAt:   time.Time{},
	}
	data, err := json.Marshal(message)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(entryPath, data, 0o600); err != nil {
		t.Fatal(err)
	}

	if err := verifier.VerifySmsCode(context.Background(), "code-hash", "73104", extraData); err != mtproto.ErrPhoneCodeInvalid {
		t.Fatalf("expected expired code to be rejected, got %v", err)
	}
	if _, err := os.Stat(entryPath); !os.IsNotExist(err) {
		t.Fatalf("expected expired outbox entry to be removed, stat error: %v", err)
	}
}

func TestLocalFileVerifierDoesNotChangeExistingDirectoryPermissions(t *testing.T) {
	outbox := filepath.Join(t.TempDir(), "outbox")
	if err := os.Mkdir(outbox, 0o755); err != nil {
		t.Fatal(err)
	}
	verifier := New(&conf.SmsVerifyCodeConfig{LocalOutboxDir: outbox})
	if _, err := verifier.SendSmsVerifyCode(context.Background(), "+15551234567", "73104", "code-hash"); err == nil {
		t.Fatal("expected insecure existing directory to be rejected")
	}
	info, err := os.Stat(outbox)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0o755 {
		t.Fatalf("expected existing directory permissions to remain 0755, got %04o", info.Mode().Perm())
	}
}

func TestLocalFileVerifierRequiresAbsoluteOutbox(t *testing.T) {
	verifier := New(&conf.SmsVerifyCodeConfig{LocalOutboxDir: "relative/outbox"})
	if _, err := verifier.SendSmsVerifyCode(context.Background(), "+15551234567", "73104", "code-hash"); err == nil {
		t.Fatal("expected relative outbox path to be rejected")
	}
}
