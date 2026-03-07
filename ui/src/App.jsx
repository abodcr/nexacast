import React, { useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

const emptyForm = {
  id: "",
  name: "",
  source_url: "",
  enabled: true,
  profile: "copy",
};

function LoginView({ onLoggedIn }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await api("/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      onLoggedIn();
    } catch (error) {
      setErr(String(error.message || error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "#0b1020", color: "#fff" }}>
      <form
        onSubmit={submit}
        style={{
          width: 360,
          background: "#121a2f",
          border: "1px solid #24304f",
          borderRadius: 16,
          padding: 24,
          boxSizing: "border-box",
        }}
      >
        <h1 style={{ marginTop: 0, marginBottom: 8 }}>StreamBox Admin</h1>
        <div style={{ color: "#9fb0d0", marginBottom: 20 }}>Login to manage channels</div>

        {err ? (
          <div style={{ background: "#4a1212", color: "#fff", padding: 10, borderRadius: 8, marginBottom: 14 }}>
            {err}
          </div>
        ) : null}

        <label style={{ display: "block", marginBottom: 6 }}>Username</label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          style={inputStyle}
          autoComplete="username"
        />

        <label style={{ display: "block", marginBottom: 6 }}>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={inputStyle}
          autoComplete="current-password"
        />

        <button type="submit" disabled={busy} style={primaryButtonStyle}>
          {busy ? "Logging in..." : "Login"}
        </button>
      </form>
    </div>
  );
}

function DashboardView({ me, onLogout }) {
  const [channels, setChannels] = useState([]);
  const [stats, setStats] = useState({ total: 0, running: 0, stopped: 0, error: 0, disabled: 0 });
  const [form, setForm] = useState(emptyForm);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedLog, setSelectedLog] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [search, setSearch] = useState("");

  async function refresh() {
    const [channelList, statData] = await Promise.all([api("/channels"), api("/stats")]);
    setChannels(channelList);
    setStats(statData);
  }

  useEffect(() => {
    refresh().catch((e) => setErr(String(e.message || e)));
    const timer = setInterval(() => {
      refresh().catch(() => {});
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  async function add() {
    setBusy(true);
    setErr("");
    try {
      await api("/channels", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setForm(emptyForm);
      await refresh();
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function startChannel(id) {
    setBusy(true);
    setErr("");
    try {
      await api(`/channels/${id}/start`, { method: "POST" });
      await refresh();
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function stopChannel(id) {
    setBusy(true);
    setErr("");
    try {
      await api(`/channels/${id}/stop`, { method: "POST" });
      await refresh();
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function deleteChannel(id) {
    setBusy(true);
    setErr("");
    try {
      await api(`/channels/${id}`, { method: "DELETE" });
      if (selectedLog?.channel_id === id) {
        setSelectedLog(null);
      }
      if (previewUrl.includes(`/live/${id}/`)) {
        setPreviewUrl("");
      }
      await refresh();
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function loadLog(id) {
    setErr("");
    try {
      const data = await api(`/channels/${id}/log`);
      setSelectedLog(data);
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  async function logout() {
    try {
      await api("/logout", { method: "POST" });
    } finally {
      onLogout();
    }
  }

  const filteredChannels = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return channels;
    return channels.filter((ch) =>
      [ch.id, ch.name, ch.source_url, ch.profile, ch.status]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(q)
    );
  }, [channels, search]);

  return (
    <div style={{ fontFamily: "Arial, sans-serif", minHeight: "100vh", background: "#0f172a", color: "#e5e7eb" }}>
      <div style={{ maxWidth: 1400, margin: "0 auto", padding: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, marginBottom: 20 }}>
          <div>
            <h1 style={{ margin: 0 }}>StreamBox Pro</h1>
            <div style={{ color: "#94a3b8", marginTop: 6 }}>
              Logged in as <b>{me?.username}</b>
            </div>
          </div>
          <button onClick={logout} style={dangerButtonStyle}>Logout</button>
        </div>

        {err ? (
          <div style={{ background: "#4a1212", color: "#fff", padding: 12, marginBottom: 16, borderRadius: 10 }}>
            {err}
          </div>
        ) : null}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 14, marginBottom: 20 }}>
          <StatCard title="Total" value={stats.total} />
          <StatCard title="Running" value={stats.running} />
          <StatCard title="Stopped" value={stats.stopped} />
          <StatCard title="Errors" value={stats.error} />
          <StatCard title="Disabled" value={stats.disabled} />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "420px 1fr", gap: 20 }}>
          <div style={panelStyle}>
            <h2 style={h2Style}>Add / Update Channel</h2>

            <label style={labelStyle}>ID</label>
            <input
              value={form.id}
              onChange={(e) => setForm({ ...form, id: e.target.value })}
              style={inputStyleDark}
            />

            <label style={labelStyle}>Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              style={inputStyleDark}
            />

            <label style={labelStyle}>Source URL</label>
            <input
              value={form.source_url}
              onChange={(e) => setForm({ ...form, source_url: e.target.value })}
              style={inputStyleDark}
            />

            <label style={labelStyle}>Profile</label>
            <select
              value={form.profile}
              onChange={(e) => setForm({ ...form, profile: e.target.value })}
              style={inputStyleDark}
            >
              <option value="copy">copy</option>
              <option value="audio_aac_fix">audio_aac_fix</option>
              <option value="transcode_720p">transcode_720p</option>
              <option value="transcode_480p">transcode_480p</option>
            </select>

            <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              />
              Enabled
            </label>

            <button onClick={add} disabled={busy} style={primaryButtonStyle}>
              Save Channel
            </button>
          </div>

          <div style={panelStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", marginBottom: 14 }}>
              <h2 style={h2Style}>Channels</h2>
              <input
                placeholder="Search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ ...inputStyleDark, marginBottom: 0, maxWidth: 260 }}
              />
            </div>

            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 1100 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #26324b", color: "#93a4c3" }}>
                    <th align="left" style={thStyle}>ID</th>
                    <th align="left" style={thStyle}>Name</th>
                    <th align="left" style={thStyle}>Profile</th>
                    <th align="left" style={thStyle}>Enabled</th>
                    <th align="left" style={thStyle}>Status</th>
                    <th align="left" style={thStyle}>Segments</th>
                    <th align="left" style={thStyle}>Restarts</th>
                    <th align="left" style={thStyle}>HLS</th>
                    <th align="left" style={thStyle}>Error</th>
                    <th align="left" style={thStyle}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredChannels.map((ch) => (
                    <tr key={ch.id} style={{ borderTop: "1px solid #1c2740" }}>
                      <td style={tdStyle}>{ch.id}</td>
                      <td style={tdStyle}>{ch.name}</td>
                      <td style={tdStyle}>{ch.profile}</td>
                      <td style={tdStyle}>{ch.enabled ? "yes" : "no"}</td>
                      <td style={tdStyle}>
                        <span style={statusBadge(ch.status)}>{ch.status}</span>
                      </td>
                      <td style={tdStyle}>{ch.segment_count}</td>
                      <td style={tdStyle}>{ch.restart_count}</td>
                      <td style={tdStyle}>
                        <a href={ch.hls_url} target="_blank" rel="noreferrer" style={{ color: "#60a5fa" }}>
                          open
                        </a>
                      </td>
                      <td style={{ ...tdStyle, maxWidth: 260, wordBreak: "break-word", color: "#fca5a5" }}>
                        {ch.last_error || "-"}
                      </td>
                      <td style={{ ...tdStyle, display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <button onClick={() => startChannel(ch.id)} disabled={busy} style={smallButtonStyle}>Start</button>
                        <button onClick={() => stopChannel(ch.id)} disabled={busy} style={smallButtonStyle}>Stop</button>
                        <button onClick={() => loadLog(ch.id)} disabled={busy} style={smallButtonStyle}>Log</button>
                        <button onClick={() => setPreviewUrl(ch.hls_url)} disabled={busy} style={smallButtonStyle}>Preview</button>
                        <button onClick={() => deleteChannel(ch.id)} disabled={busy} style={dangerSmallButtonStyle}>Delete</button>
                      </td>
                    </tr>
                  ))}
                  {filteredChannels.length === 0 ? (
                    <tr>
                      <td colSpan="10" style={{ padding: 20, textAlign: "center", color: "#94a3b8" }}>
                        No channels
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginTop: 20 }}>
          <div style={panelStyle}>
            <h2 style={h2Style}>Preview</h2>
            {previewUrl ? (
              <video
                controls
                autoPlay
                muted
                style={{ width: "100%", borderRadius: 10, background: "#000" }}
                src={previewUrl}
              />
            ) : (
              <div style={{ color: "#94a3b8" }}>Select a channel preview</div>
            )}
          </div>

          <div style={panelStyle}>
            <h2 style={h2Style}>Log Viewer</h2>
            {selectedLog ? (
              <>
                <div style={{ marginBottom: 10 }}>Channel: <b>{selectedLog.channel_id}</b></div>
                <div style={{ marginBottom: 10 }}>Status: <b>{selectedLog.status}</b></div>
                <div style={{ marginBottom: 10 }}>Running: <b>{String(selectedLog.running)}</b></div>
                <div style={{ marginBottom: 10 }}>Last error: <b>{selectedLog.last_error || "-"}</b></div>
                <pre
                  style={{
                    background: "#020617",
                    color: "#86efac",
                    padding: 12,
                    borderRadius: 8,
                    overflow: "auto",
                    whiteSpace: "pre-wrap",
                    minHeight: 260,
                    margin: 0,
                  }}
                >
                  {selectedLog.tail || "No log data"}
                </pre>
              </>
            ) : (
              <div style={{ color: "#94a3b8" }}>Select a channel log</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);

  async function loadMe() {
    try {
      const data = await api("/me");
      setMe(data.user);
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMe();
  }, []);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "#0f172a", color: "#fff" }}>
        Loading...
      </div>
    );
  }

  if (!me) {
    return <LoginView onLoggedIn={loadMe} />;
  }

  return <DashboardView me={me} onLogout={() => setMe(null)} />;
}

function StatCard({ title, value }) {
  return (
    <div style={panelStyle}>
      <div style={{ color: "#94a3b8", fontSize: 14, marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 32, fontWeight: "bold" }}>{value}</div>
    </div>
  );
}

const panelStyle = {
  background: "#111827",
  border: "1px solid #253047",
  borderRadius: 14,
  padding: 16,
};

const h2Style = {
  marginTop: 0,
  marginBottom: 14,
};

const labelStyle = {
  display: "block",
  marginBottom: 6,
  color: "#cbd5e1",
};

const inputStyle = {
  width: "100%",
  marginBottom: 14,
  padding: 10,
  borderRadius: 10,
  border: "1px solid #34435f",
  boxSizing: "border-box",
};

const inputStyleDark = {
  width: "100%",
  marginBottom: 14,
  padding: 10,
  borderRadius: 10,
  border: "1px solid #334155",
  background: "#0f172a",
  color: "#e5e7eb",
  boxSizing: "border-box",
};

const primaryButtonStyle = {
  padding: "10px 16px",
  borderRadius: 10,
  border: "none",
  background: "#2563eb",
  color: "#fff",
  cursor: "pointer",
};

const dangerButtonStyle = {
  padding: "10px 16px",
  borderRadius: 10,
  border: "none",
  background: "#b91c1c",
  color: "#fff",
  cursor: "pointer",
};

const smallButtonStyle = {
  padding: "6px 10px",
  borderRadius: 8,
  border: "1px solid #334155",
  background: "#1e293b",
  color: "#fff",
  cursor: "pointer",
};

const dangerSmallButtonStyle = {
  padding: "6px 10px",
  borderRadius: 8,
  border: "1px solid #7f1d1d",
  background: "#7f1d1d",
  color: "#fff",
  cursor: "pointer",
};

const thStyle = {
  padding: "10px 6px",
};

const tdStyle = {
  padding: "10px 6px",
  verticalAlign: "top",
};

function statusBadge(status) {
  const common = {
    display: "inline-block",
    padding: "4px 8px",
    borderRadius: 999,
    fontSize: 12,
    fontWeight: "bold",
  };

  if (status === "running") {
    return { ...common, background: "#14532d", color: "#bbf7d0" };
  }
  if (status === "error") {
    return { ...common, background: "#7f1d1d", color: "#fecaca" };
  }
  if (status === "starting") {
    return { ...common, background: "#78350f", color: "#fde68a" };
  }
  return { ...common, background: "#334155", color: "#cbd5e1" };
}
