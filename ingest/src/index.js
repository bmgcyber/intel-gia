// Accepts one daily packet and commits it as inbox/YYYY-MM-DD.json.
// The raw body is stored unchanged: apply_packet.py hashes those bytes.
// This worker does not run the checker. Publish does, after the commit.

const MAX_BYTES = 1_000_000;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/") {
      return Response.json({ ok: true });
    }
    if (url.pathname !== "/inbox") {
      return Response.json({ error: "POST /inbox" }, { status: 404 });
    }
    if (request.method !== "POST") {
      return Response.json({ error: "POST /inbox" }, { status: 405 });
    }
    try {
      return await filePacket(request, env);
    } catch (error) {
      const message = error instanceof Error ? error.message : "request failed";
      console.error(JSON.stringify({ message: "unhandled error", error: message }));
      return Response.json({ error: "request failed" }, { status: 500 });
    }
  },
};

async function filePacket(request, env) {
  if (!env.INGEST_SECRET) {
    console.error(JSON.stringify({ message: "INGEST_SECRET is not set" }));
    return Response.json({ error: "ingest is not configured" }, { status: 503 });
  }
  const header = request.headers.get("Authorization") ?? "";
  if (!(await bearerOk(header, env.INGEST_SECRET))) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }
  if (!env.GITHUB_TOKEN) {
    console.error(JSON.stringify({ message: "GITHUB_TOKEN is not set" }));
    return Response.json({ error: "ingest is not configured" }, { status: 503 });
  }

  const rawBytes = new Uint8Array(await request.arrayBuffer());
  if (rawBytes.byteLength === 0 || rawBytes.byteLength > MAX_BYTES) {
    return Response.json({ error: "body must be a JSON packet under 1 MB" }, { status: 400 });
  }
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(rawBytes);
  } catch {
    return Response.json({ error: "body is not UTF-8" }, { status: 400 });
  }
  let packet;
  try {
    packet = JSON.parse(text);
  } catch {
    return Response.json({ error: "body is not JSON" }, { status: 400 });
  }
  if (!packet || typeof packet !== "object" || Array.isArray(packet)) {
    return Response.json({ error: "packet must be a JSON object" }, { status: 400 });
  }
  const edition = packet.edition;
  if (!isRealEdition(edition)) {
    return Response.json({ error: "edition must be a real YYYY-MM-DD" }, { status: 400 });
  }

  const owner = env.GITHUB_OWNER || "bmgcyber";
  const repo = env.GITHUB_REPO || "intel-gia";
  const branch = env.GITHUB_BRANCH || "main";
  const path = `inbox/${edition}.json`;
  const api = `https://api.github.com/repos/${owner}/${repo}/contents/${path}`;
  const existing = await github(env, "GET", `${api}?ref=${encodeURIComponent(branch)}`);
  let sha;
  if (existing.status === 200 && existing.payload && typeof existing.payload.content === "string") {
    if (sameBytes(decodeBase64(existing.payload.content), rawBytes)) {
      console.log(JSON.stringify({ message: "inbox unchanged", edition, path }));
      return Response.json({ status: "unchanged", edition, path });
    }
    sha = existing.payload.sha;
  } else if (existing.status !== 404) {
    console.error(JSON.stringify({ message: "inbox read failed", edition, github: existing.status }));
    return Response.json(
      { error: "could not read the inbox file", github: existing.payload?.message ?? existing.status },
      { status: 502 },
    );
  }

  const put = await github(env, "PUT", api, {
    message: `Inbox ${edition}`,
    content: encodeBase64(rawBytes),
    branch,
    ...(sha ? { sha } : {}),
  });
  if (!put.ok) {
    console.error(JSON.stringify({ message: "inbox write failed", edition, github: put.status }));
    return Response.json(
      { error: "could not commit the inbox file", github: put.payload?.message ?? put.status },
      { status: 502 },
    );
  }
  console.log(JSON.stringify({ message: "inbox filed", edition, path }));
  return Response.json({
    status: "filed",
    edition,
    path,
    commit: put.payload?.commit?.sha ?? null,
  });
}

export function isRealEdition(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

async function bearerOk(header, secret) {
  const provided = header.startsWith("Bearer ") ? header.slice("Bearer ".length) : "";
  if (!provided) return false;
  const encoder = new TextEncoder();
  const [left, right] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(provided)),
    crypto.subtle.digest("SHA-256", encoder.encode(secret)),
  ]);
  const actual = new Uint8Array(left);
  const expected = new Uint8Array(right);
  if (typeof crypto.subtle.timingSafeEqual === "function") {
    return crypto.subtle.timingSafeEqual(actual, expected);
  }
  let diff = 0;
  for (let i = 0; i < actual.length; i++) diff |= actual[i] ^ expected[i];
  return diff === 0;
}

async function github(env, method, url, body) {
  const response = await fetch(url, {
    method,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "User-Agent": "GIA-ingest",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { message: text.slice(0, 300) };
    }
  }
  return { ok: response.ok, status: response.status, payload };
}

function encodeBase64(bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function decodeBase64(text) {
  const binary = atob(text.replace(/\s/g, ""));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function sameBytes(left, right) {
  if (left.byteLength !== right.byteLength) return false;
  let diff = 0;
  for (let i = 0; i < left.byteLength; i++) diff |= left[i] ^ right[i];
  return diff === 0;
}
