package core

import (
	"fmt"
	"net"
	"strconv"
	"strings"

	"github.com/zeromicro/go-zero/rest"
)

func dfsFileURL(conf rest.RestConf, creatorID, fileID int64, extension string) string {
	host := strings.TrimSpace(conf.Host)
	switch host {
	case "", "0.0.0.0":
		host = "127.0.0.1"
	case "::":
		host = "::1"
	}

	scheme := "http"
	if conf.CertFile != "" || conf.KeyFile != "" {
		scheme = "https"
	}

	return fmt.Sprintf("%s://%s/dfs/file/%d_%d.%s",
		scheme,
		net.JoinHostPort(host, strconv.Itoa(conf.Port)),
		creatorID,
		fileID,
		extension)
}
