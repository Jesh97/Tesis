import { LoginBranding } from '../components/LoginBranding'
import { LoginForm } from '../components/LoginForm'

export function LoginPage() {
  return (
    <main className="flex min-h-svh items-center justify-center bg-slate-100 p-4">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-2xl bg-white shadow-xl md:grid-cols-2 md:h-[520px]">
        <LoginBranding />
        <LoginForm />
      </div>
    </main>
  )
}
