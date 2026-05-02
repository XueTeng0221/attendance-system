import { useState } from "react";
import type { FormEvent } from "react";

import { login } from "../api/client";
import { setCachedUser, setToken } from "../auth";
import type { CurrentUser } from "../types";

interface LoginPageProps {
  onLoggedIn: (user: CurrentUser) => void;
}

export default function LoginPage({ onLoggedIn }: LoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const data = await login(username.trim(), password);
      setToken(data.access_token);
      setCachedUser(data.user);
      onLoggedIn(data.user);
    } catch (err) {
      const detail =
        typeof err === "object" && err && "response" in err
          ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ((err as any).response?.data?.detail as string | undefined)
          : undefined;
      setError(detail || "登录失败，请检查账号或网络");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-shell">
      <div className="login-card">
        <p className="hero-eyebrow">Class Attendance · Login</p>
        <h1>欢迎回到考勤平台</h1>
        <p className="panel-subtitle">教师可管理学生与查看报表，学生仅可进行本人考勤。</p>

        <form className="form-grid" onSubmit={handleSubmit}>
          <label>
            账号
            <input
              autoFocus
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </label>
          <label>
            密码
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <button className="btn btn-accent" type="submit" disabled={submitting}>
            {submitting ? "登录中..." : "登录"}
          </button>
        </form>

        {error ? <p className="error-text">{error}</p> : null}

        <p className="login-hint">
          初始教师账号：<code>admin</code> / <code>admin123</code>，登录后请尽快修改。
        </p>
      </div>
    </div>
  );
}
