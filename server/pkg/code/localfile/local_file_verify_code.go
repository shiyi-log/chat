// Copyright 2026 Private Chat Authors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package localfile

import (
	"context"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/teamgram/proto/mtproto"
	"github.com/teamgram/teamgram-server/pkg/code/conf"
)

const codeLifetime = 3 * time.Minute

type localFileVerifyCode struct {
	outboxDir string
	mu        sync.Mutex
}

type outboxMessage struct {
	PhoneNumber string    `json:"phone_number"`
	PhoneCode   string    `json:"phone_code"`
	CodeHash    string    `json:"phone_code_hash"`
	ExpiresAt   time.Time `json:"expires_at"`
}

func New(c *conf.SmsVerifyCodeConfig) *localFileVerifyCode {
	if c == nil {
		c = new(conf.SmsVerifyCodeConfig)
	}
	return &localFileVerifyCode{outboxDir: c.LocalOutboxDir}
}

func (m *localFileVerifyCode) SendSmsVerifyCode(ctx context.Context, phoneNumber, code, codeHash string) (string, error) {
	if err := ctx.Err(); err != nil {
		return "", err
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	if phoneNumber == "" || code == "" || codeHash == "" {
		return "", errors.New("phone number, code, and code hash are required")
	}
	dir, err := m.ensureOutbox()
	if err != nil {
		return "", err
	}
	message := outboxMessage{
		PhoneNumber: phoneNumber,
		PhoneCode:   code,
		CodeHash:    codeHash,
		ExpiresAt:   time.Now().Add(codeLifetime),
	}
	data, err := json.Marshal(message)
	if err != nil {
		return "", fmt.Errorf("encode local verification message: %w", err)
	}
	file, err := os.CreateTemp(dir, ".pending-*")
	if err != nil {
		return "", fmt.Errorf("create local verification message: %w", err)
	}
	tmpPath := file.Name()
	defer os.Remove(tmpPath)
	if err := file.Chmod(0o600); err != nil {
		_ = file.Close()
		return "", fmt.Errorf("set local verification message permissions: %w", err)
	}
	if _, err := file.Write(data); err != nil {
		_ = file.Close()
		return "", fmt.Errorf("write local verification message: %w", err)
	}
	if err := file.Sync(); err != nil {
		_ = file.Close()
		return "", fmt.Errorf("sync local verification message: %w", err)
	}
	if err := file.Close(); err != nil {
		return "", fmt.Errorf("close local verification message: %w", err)
	}
	if err := os.Rename(tmpPath, filepath.Join(dir, messageFilename(codeHash))); err != nil {
		return "", fmt.Errorf("publish local verification message: %w", err)
	}
	return code, nil
}

func (m *localFileVerifyCode) VerifySmsCode(ctx context.Context, codeHash, code, extraData string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if codeHash == "" || code == "" || subtle.ConstantTimeCompare([]byte(code), []byte(extraData)) != 1 {
		return mtproto.ErrPhoneCodeInvalid
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	dir, err := m.ensureOutbox()
	if err != nil {
		return err
	}
	path := filepath.Join(dir, messageFilename(codeHash))
	data, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return mtproto.ErrPhoneCodeInvalid
		}
		return fmt.Errorf("read local verification message: %w", err)
	}
	var message outboxMessage
	if err := json.Unmarshal(data, &message); err != nil {
		return fmt.Errorf("decode local verification message: %w", err)
	}
	if message.CodeHash != codeHash {
		return mtproto.ErrPhoneCodeInvalid
	}
	if time.Now().After(message.ExpiresAt) {
		if err := os.Remove(path); err != nil {
			if errors.Is(err, os.ErrNotExist) {
				return mtproto.ErrPhoneCodeInvalid
			}
			return fmt.Errorf("remove expired local verification message: %w", err)
		}
		return mtproto.ErrPhoneCodeInvalid
	}
	if subtle.ConstantTimeCompare([]byte(message.PhoneCode), []byte(code)) != 1 {
		return mtproto.ErrPhoneCodeInvalid
	}
	if err := os.Remove(path); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return mtproto.ErrPhoneCodeInvalid
		}
		return fmt.Errorf("consume local verification message: %w", err)
	}
	return nil
}

func (m *localFileVerifyCode) ensureOutbox() (string, error) {
	if !filepath.IsAbs(m.outboxDir) || strings.TrimSpace(m.outboxDir) == "" {
		return "", errors.New("local verification outbox must be an absolute path")
	}
	dir := filepath.Clean(m.outboxDir)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return "", fmt.Errorf("create local verification outbox: %w", err)
	}
	info, err := os.Lstat(dir)
	if err != nil {
		return "", fmt.Errorf("inspect local verification outbox: %w", err)
	}
	if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return "", errors.New("local verification outbox must be a real directory")
	}
	if info.Mode().Perm() != 0o700 {
		return "", errors.New("local verification outbox must have permissions 0700")
	}
	return dir, nil
}

func messageFilename(codeHash string) string {
	digest := sha256.Sum256([]byte(codeHash))
	return hex.EncodeToString(digest[:]) + ".json"
}
