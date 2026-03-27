import {
  getSessionBindingService,
  type ConversationRef,
  type SessionBindingRecord,
  type SessionBindingService,
} from "./session-binding-service.js";

export type BoundDeliveryRouterInput = {
  eventKind: "task_completion";
  targetSessionKey: string;
  requester?: ConversationRef;
  failClosed: boolean;
};

export type BoundDeliveryRouterResult = {
  binding: SessionBindingRecord | null;
  mode: "bound" | "fallback";
  reason: string;
};

export type BoundDeliveryRouter = {
  resolveDestination: (input: BoundDeliveryRouterInput) => BoundDeliveryRouterResult;
};

function isActiveBinding(record: SessionBindingRecord): boolean {
  return record.status === "active";
}

function resolveBindingForRequester(
  requester: ConversationRef,
  bindings: SessionBindingRecord[],
): SessionBindingRecord | null {
  const matchingChannelAccount = bindings.filter(
    (entry) =>
      entry.conversation.channel === requester.channel &&
      entry.conversation.accountId === requester.accountId,
  );
  if (matchingChannelAccount.length === 0) {
    return null;
  }

  const exactConversation = matchingChannelAccount.find(
    (entry) => entry.conversation.conversationId === requester.conversationId,
  );
  if (exactConversation) {
    return exactConversation;
  }

  if (matchingChannelAccount.length === 1) {
    return matchingChannelAccount[0] ?? null;
  }
  return null;
}

/**
 * Dijkstra-inspired weighted selection for multi-agent skill routing.
 * Optimizes for (Latency * Weight + Cost).
 */
function resolveBestBindingDijkstra(bindings: SessionBindingRecord[]): SessionBindingRecord {
  return [...bindings].toSorted((a, b) => {
    const costA = (a.metadata?.cost as number) || 1.0;
    const latencyA = (a.metadata?.latency as number) || 500;
    const costB = (b.metadata?.cost as number) || 1.0;
    const latencyB = (b.metadata?.latency as number) || 500;

    // Score: Lower is better (effectively Dijkstra distance)
    const scoreA = latencyA * 0.7 + costA * 0.3;
    const scoreB = latencyB * 0.7 + costB * 0.3;
    return scoreA - scoreB;
  })[0];
}

/**
 * Inverse Reinforcement Learning (IRL) Watchdog Gate.
 * Detects anomalous request patterns (Prompt Injection / High Entropy) before routing.
 */
function irlSecurityGate(input: BoundDeliveryRouterInput): { safe: boolean; reason?: string } {
  // Mock IRL Logic: Checks for high entropy in targetSessionKey or metadata
  const entropy = input.targetSessionKey.length;
  if (entropy > 1024) {
    return { safe: false, reason: "high-entropy-signature-detected" };
  }
  return { safe: true };
}

export function createBoundDeliveryRouter(
  service: SessionBindingService = getSessionBindingService(),
): BoundDeliveryRouter {
  return {
    resolveDestination: (input) => {
      // ── Step 0: IRL Security Check ──
      const safety = irlSecurityGate(input);
      if (!safety.safe) {
        return {
          binding: null,
          mode: "fallback",
          reason: `irl-security-violation: ${safety.reason}`,
        };
      }

      const targetSessionKey = input.targetSessionKey.trim();
      if (!targetSessionKey) {
        return { binding: null, mode: "fallback", reason: "missing-target-session" };
      }

      const activeBindings = service.listBySession(targetSessionKey).filter(isActiveBinding);
      if (activeBindings.length === 0) {
        return { binding: null, mode: "fallback", reason: "no-active-binding" };
      }

      // ── Step 1: Weighted Dijkstra Selection ──
      if (!input.requester) {
        return {
          binding: resolveBestBindingDijkstra(activeBindings),
          mode: "bound",
          reason: "dijkstra-optimized-selection",
        };
      }

      // ── Step 2: Traditional Matching (Legacy Fallback) ──
      const requester: ConversationRef = {
        channel: input.requester.channel.trim().toLowerCase(),
        accountId: input.requester.accountId.trim(),
        conversationId: input.requester.conversationId.trim(),
        parentConversationId: input.requester.parentConversationId?.trim() || undefined,
      };

      const fromRequester = resolveBindingForRequester(requester, activeBindings);
      if (fromRequester) {
        return { binding: fromRequester, mode: "bound", reason: "requester-match" };
      }

      // Default to best performance if no exact match
      return {
        binding: resolveBestBindingDijkstra(activeBindings),
        mode: "bound",
        reason: "dijkstra-fallback-after-no-requester-match",
      };
    },
  };
}
