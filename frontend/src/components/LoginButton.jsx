import { loginUrl } from '../api'

export default function LoginButton() {
  return (
    <section className="card login-card">
      <h2>Sign in</h2>
      <p className="muted">Sign in with Google to see your transactions.</p>
      <a className="login-button" href={loginUrl()}>
        Sign in with Google
      </a>
    </section>
  )
}
