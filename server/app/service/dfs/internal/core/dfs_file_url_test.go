package core

import (
	"testing"

	"github.com/zeromicro/go-zero/rest"
)

func TestDfsFileURLUsesMiniHTTPConfig(t *testing.T) {
	tests := []struct {
		name string
		conf rest.RestConf
		want string
	}{
		{
			name: "configured host and port",
			conf: rest.RestConf{Host: "10.0.0.9", Port: 24000},
			want: "http://10.0.0.9:24000/dfs/file/17_23.gif",
		},
		{
			name: "wildcard bind host targets loopback",
			conf: rest.RestConf{Host: "0.0.0.0", Port: 11701},
			want: "http://127.0.0.1:11701/dfs/file/17_23.gif",
		},
		{
			name: "empty bind host targets loopback",
			conf: rest.RestConf{Port: 24000},
			want: "http://127.0.0.1:24000/dfs/file/17_23.gif",
		},
		{
			name: "IPv6 wildcard bind host targets loopback",
			conf: rest.RestConf{Host: "::", Port: 24000},
			want: "http://[::1]:24000/dfs/file/17_23.gif",
		},
		{
			name: "IPv6 host",
			conf: rest.RestConf{Host: "2001:db8::9", Port: 24000},
			want: "http://[2001:db8::9]:24000/dfs/file/17_23.gif",
		},
		{
			name: "configured TLS",
			conf: rest.RestConf{Host: "dfs.internal", Port: 24443, CertFile: "tls.crt", KeyFile: "tls.key"},
			want: "https://dfs.internal:24443/dfs/file/17_23.gif",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := dfsFileURL(tt.conf, 17, 23, "gif"); got != tt.want {
				t.Fatalf("dfsFileURL() = %q, want %q", got, tt.want)
			}
		})
	}
}

func TestDfsFileURLPreservesMediaExtension(t *testing.T) {
	tests := []struct {
		extension string
		want      string
	}{
		{extension: "mp4", want: "http://127.0.0.1:24000/dfs/file/31_47.mp4"},
		{extension: "mp3", want: "http://127.0.0.1:24000/dfs/file/31_47.mp3"},
	}

	for _, tt := range tests {
		t.Run(tt.extension, func(t *testing.T) {
			if got := dfsFileURL(rest.RestConf{Host: "127.0.0.1", Port: 24000}, 31, 47, tt.extension); got != tt.want {
				t.Fatalf("dfsFileURL() = %q, want %q", got, tt.want)
			}
		})
	}
}
