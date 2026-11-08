package dao

import (
	"testing"

	sessionclient "github.com/teamgram/teamgram-server/app/interface/session/client"
	"github.com/zeromicro/go-zero/core/hash"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type namedSessionClient struct {
	sessionclient.SessionClient
	node string
}

func TestInvokeByKeyRetainsSoleNodeAfterConnectionErrors(t *testing.T) {
	const (
		node = "session-1"
		key  = "auth-key"
	)

	sess := &ShardingSessionClient{
		dispatcher:   hash.NewConsistentHash(),
		sessions:     map[string]sessionclient.SessionClient{node: namedSessionClient{node: node}},
		failCounters: make(map[string]int),
	}
	sess.dispatcher.Add(node)

	for i := 0; i < maxNodeFailures; i++ {
		err := sess.InvokeByKey(key, func(sessionclient.SessionClient) error {
			return status.Error(codes.Unavailable, "temporarily unavailable")
		})
		if status.Code(err) != codes.Unavailable {
			t.Fatalf("InvokeByKey() error = %v, want Unavailable on failure %d", err, i+1)
		}
	}

	err := sess.InvokeByKey(key, func(sessionclient.SessionClient) error { return nil })
	if err != nil {
		t.Fatalf("InvokeByKey() after recovery error = %v, want nil", err)
	}
	if _, ok := sess.dispatcher.Get(key); !ok {
		t.Fatal("sole session node was removed from the dispatcher")
	}
}

func TestInvokeByKeyRemovesFailedNodeWhenAnotherNodeExists(t *testing.T) {
	const (
		node1 = "session-1"
		node2 = "session-2"
		key   = "auth-key"
	)

	sess := &ShardingSessionClient{
		dispatcher: hash.NewConsistentHash(),
		sessions: map[string]sessionclient.SessionClient{
			node1: namedSessionClient{node: node1},
			node2: namedSessionClient{node: node2},
		},
		failCounters: make(map[string]int),
	}
	sess.dispatcher.Add(node1)
	sess.dispatcher.Add(node2)

	initial, ok := sess.dispatcher.Get(key)
	if !ok {
		t.Fatal("dispatcher has no initial route")
	}
	failedNode := initial.(string)
	otherNode := node1
	if failedNode == node1 {
		otherNode = node2
	}

	for i := 0; i < maxNodeFailures; i++ {
		err := sess.InvokeByKey(key, func(cli sessionclient.SessionClient) error {
			if cli.(namedSessionClient).node == failedNode {
				return status.Error(codes.Unavailable, "temporarily unavailable")
			}
			return nil
		})
		if i < maxNodeFailures-1 && status.Code(err) != codes.Unavailable {
			t.Fatalf("InvokeByKey() error = %v, want Unavailable before failure threshold", err)
		}
		if i == maxNodeFailures-1 && err != nil {
			t.Fatalf("InvokeByKey() fallback error = %v, want nil", err)
		}
	}

	routed, ok := sess.dispatcher.Get(key)
	if !ok || routed.(string) != otherNode {
		t.Fatalf("dispatcher route = %v, want remaining node %q", routed, otherNode)
	}
	if _, ok := sess.sessions[failedNode]; ok {
		t.Fatalf("failed node %q remains in the session client map", failedNode)
	}
}
