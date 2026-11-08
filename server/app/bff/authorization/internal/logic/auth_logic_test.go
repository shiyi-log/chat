package logic

import (
	"context"
	"errors"
	"testing"

	"github.com/teamgram/proto/mtproto"
	"github.com/teamgram/teamgram-server/app/bff/authorization/model"
)

type verifyCodeStub struct {
	verifyCalls int
	gotHash     string
	gotCode     string
	gotExtra    string
	err         error
}

func (s *verifyCodeStub) SendSmsVerifyCode(context.Context, string, string, string) (string, error) {
	return "", nil
}

func (s *verifyCodeStub) VerifySmsCode(_ context.Context, hash, code, extra string) error {
	s.verifyCalls++
	s.gotHash = hash
	s.gotCode = code
	s.gotExtra = extra
	return s.err
}

func TestVerifyPhoneCodeAcceptsDeliveredAppCodeWithoutSmsProvider(t *testing.T) {
	provider := &verifyCodeStub{}
	auth := &AuthLogic{VerifyCodeInterface: provider}
	codeData := &model.PhoneCodeTransaction{
		SentCodeType:       model.SentCodeTypeApp,
		PhoneCodeExtraData: "delivered-code",
	}

	if err := auth.VerifyPhoneCode(context.Background(), codeData, "delivered-code"); err != nil {
		t.Fatalf("VerifyPhoneCode() error = %v", err)
	}
	if provider.verifyCalls != 0 {
		t.Fatalf("SMS provider calls = %d, want 0 for an app-delivered code", provider.verifyCalls)
	}
}

func TestVerifyPhoneCodeRejectsWrongDeliveredAppCode(t *testing.T) {
	provider := &verifyCodeStub{}
	auth := &AuthLogic{VerifyCodeInterface: provider}
	codeData := &model.PhoneCodeTransaction{
		SentCodeType:       model.SentCodeTypeApp,
		PhoneCodeExtraData: "delivered-code",
	}

	err := auth.VerifyPhoneCode(context.Background(), codeData, "wrong-code")
	if err != mtproto.ErrPhoneCodeInvalid {
		t.Fatalf("VerifyPhoneCode() error = %v, want PHONE_CODE_INVALID", err)
	}
	if provider.verifyCalls != 0 {
		t.Fatalf("SMS provider calls = %d, want 0 for an app-delivered code", provider.verifyCalls)
	}
}

func TestVerifyPhoneCodeDelegatesSmsVerificationToProvider(t *testing.T) {
	providerErr := errors.New("provider verification failed")
	provider := &verifyCodeStub{err: providerErr}
	auth := &AuthLogic{VerifyCodeInterface: provider}
	codeData := &model.PhoneCodeTransaction{
		SentCodeType:       model.SentCodeTypeSms,
		PhoneCodeHash:      "sms-hash",
		PhoneCodeExtraData: "provider-extra",
	}

	err := auth.VerifyPhoneCode(context.Background(), codeData, "sms-code")
	if err != providerErr {
		t.Fatalf("VerifyPhoneCode() error = %v, want provider error", err)
	}
	if provider.verifyCalls != 1 || provider.gotHash != "sms-hash" || provider.gotCode != "sms-code" || provider.gotExtra != "provider-extra" {
		t.Fatalf("SMS provider call = (%d, %q, %q, %q), want one call with the transaction values", provider.verifyCalls, provider.gotHash, provider.gotCode, provider.gotExtra)
	}
}
