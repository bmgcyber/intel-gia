import assert from "node:assert/strict";
import { test } from "node:test";
import worker, { isRealEdition } from "./index.js";

const env = {
  INGEST_SECRET: "test-secret",
  GITHUB_TOKEN: "gh-test",
  GITHUB_OWNER: "bmgcyber",
  GITHUB_REPO: "intel-gia",
  GITHUB_BRANCH: "main",
};

function post(body, { auth = "Bearer test-secret", secretEnv = env } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) headers.Authorization = auth;
  return worker.fetch(
    new Request("https://gia-ingest.example/inbox", { method: "POST", headers, body }),
    secretEnv,
  );
}

test("edition must be a real calendar date", () => {
  assert.equal(isRealEdition("2026-10-16"), true);
  assert.equal(isRealEdition("2026-02-31"), false);
  assert.equal(isRealEdition("16-10-2026"), false);
});

test("GET / is a health check and other paths are closed", async () => {
  const health = await worker.fetch(new Request("https://gia-ingest.example/"), env);
  assert.equal(health.status, 200);
  assert.deepEqual(await health.json(), { ok: true });
  const missing = await worker.fetch(new Request("https://gia-ingest.example/nope"), env);
  assert.equal(missing.status, 404);
});

test("a missing or wrong bearer is rejected before GitHub is called", async () => {
  let calls = 0;
  const original = globalThis.fetch;
  globalThis.fetch = async () => {
    calls += 1;
    throw new Error("github should not be called");
  };
  try {
    assert.equal((await post('{"edition":"2026-10-16"}', { auth: null })).status, 401);
    assert.equal((await post('{"edition":"2026-10-16"}', { auth: "Bearer nope" })).status, 401);
    const bare = { ...env, INGEST_SECRET: "" };
    assert.equal((await post('{"edition":"2026-10-16"}', { secretEnv: bare })).status, 503);
    assert.equal(calls, 0);
  } finally {
    globalThis.fetch = original;
  }
});

test("a bad packet is rejected", async () => {
  assert.equal((await post("not json")).status, 400);
  assert.equal((await post('{"edition":"2026-02-31"}')).status, 400);
  assert.equal((await post("[]")).status, 400);
});

test("a new packet is committed as inbox/YYYY-MM-DD.json", async () => {
  const seen = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    seen.push({ url, method: init.method, body: init.body });
    if (init.method === "GET") return new Response(JSON.stringify({ message: "Not Found" }), { status: 404 });
    return new Response(JSON.stringify({ commit: { sha: "abc123" } }), { status: 201 });
  };
  try {
    const response = await post('{"edition":"2026-10-16"}\n');
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), {
      status: "filed",
      edition: "2026-10-16",
      path: "inbox/2026-10-16.json",
      commit: "abc123",
    });
    const put = JSON.parse(seen[1].body);
    assert.equal(put.message, "Inbox 2026-10-16");
    assert.equal(put.branch, "main");
    assert.equal(Buffer.from(put.content, "base64").toString("utf8"), '{"edition":"2026-10-16"}\n');
    assert.equal(seen[1].url, "https://api.github.com/repos/bmgcyber/intel-gia/contents/inbox/2026-10-16.json");
  } finally {
    globalThis.fetch = original;
  }
});

test("the same bytes do not create another commit", async () => {
  const raw = '{"edition":"2026-10-16"}\n';
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    assert.equal(init.method, "GET");
    return new Response(
      JSON.stringify({ sha: "old", content: Buffer.from(raw).toString("base64") }),
      { status: 200 },
    );
  };
  try {
    const response = await post(raw);
    assert.equal(response.status, 200);
    assert.equal((await response.json()).status, "unchanged");
  } finally {
    globalThis.fetch = original;
  }
});
