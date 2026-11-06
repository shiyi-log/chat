package integration

import (
	"os/exec"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/teamgram/proto/mtproto"
	"github.com/zeromicro/go-zero/core/jsonx"
)

func TestRenderedClientConfigDecodesConfiguredTcpEndpoint(t *testing.T) {
	_, testFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("failed to locate integration test source")
	}
	serverRoot := filepath.Dir(filepath.Dir(testFile))
	script := "import sys\n" +
		"from pathlib import Path\n" +
		"sys.path.insert(0, \"integration\")\n" +
		"import prepare_local\n" +
		"ports = prepare_local._read_runtime_ports({})\n" +
		"sys.stdout.write(prepare_local._render_client_config(Path(\"teamgramd/bin/config.json\"), ports))\n"
	command := exec.Command("python3", "-c", script)
	command.Dir = serverRoot
	rendered, err := command.Output()
	if err != nil {
		t.Fatalf("render local client config: %v", err)
	}

	var config mtproto.TLConfig
	if err := jsonx.Unmarshal(rendered, &config); err != nil {
		t.Fatalf("decode rendered client config: %v", err)
	}
	if config.GetData2() == nil {
		t.Fatal("rendered client config has no data2")
	}
	options := config.GetData2().GetDcOptions()
	if len(options) != 1 {
		t.Fatalf("decoded %d dc options, want exactly one TCP option", len(options))
	}
	option := options[0]
	if option.GetId() != 1 || option.GetIpAddress() != "127.0.0.1" || option.GetPort() != 25222 {
		t.Fatalf("decoded endpoint = id:%d ip:%q port:%d, want id:1 ip:127.0.0.1 port:25222",
			option.GetId(), option.GetIpAddress(), option.GetPort())
	}
}
