import { AsyncLocalStorage } from "node:async_hooks";

/** Carries the inbound request id to the rag-api call made while handling it. */
const store = new AsyncLocalStorage<{ requestId: string }>();

export const withRequestId = <T>(requestId: string, fn: () => T): T => store.run({ requestId }, fn);
export const currentRequestId = (): string | undefined => store.getStore()?.requestId;
