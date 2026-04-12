'use client'

import { Button } from '@workspace/ui/components/button'
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldSeparator,
} from '@workspace/ui/components/field'
import { Input } from '@workspace/ui/components/input'
import { cn } from '@workspace/ui/lib/utils'
import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { Logo } from '@/components/logo'
import { appPaths } from '@/config/app-paths'
import { env } from '@/config/env'
import { authClient } from '@/lib/auth-client'

function handleGitHubSignIn() {
  void authClient.signIn.social({ provider: 'github' })
}

export function LoginForm({ className, ...props }: React.ComponentProps<'div'>) {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget
    const email = (form.elements.namedItem('email') as HTMLInputElement).value
    const password = (form.elements.namedItem('password') as HTMLInputElement).value

    setError(null)
    setLoading(true)

    const { error: signInError } = await authClient.signIn.email({ email, password })

    setLoading(false)

    if (signInError) {
      setError(signInError.message ?? 'Login failed')
      return
    }

    router.push(appPaths.home.href)
  }

  return (
    <div className={cn('flex flex-col gap-6', className)} {...props}>
      <form onSubmit={handleSubmit}>
        <FieldGroup>
          <div className="flex flex-col items-center gap-2 text-center">
            <a href={appPaths.home.href} className="flex flex-col items-center gap-2 font-medium">
              <Logo />
              <span className="sr-only">{env.NEXT_PUBLIC_APP_NAME}</span>
            </a>
            <h1 className="text-xl font-bold">
              Welcome to
              {env.NEXT_PUBLIC_APP_NAME}
            </h1>
            <FieldDescription>
              Don&apos;t have an account? <a href={appPaths.auth.signup.getHref()}>Sign up</a>
            </FieldDescription>
          </div>
          <Field>
            <FieldLabel htmlFor="email">Email</FieldLabel>
            <Input id="email" name="email" type="email" placeholder="m@example.com" required />
          </Field>
          <Field>
            <FieldLabel htmlFor="password">Password</FieldLabel>
            <Input id="password" name="password" type="password" required />
          </Field>
          {error && <FieldDescription className="text-destructive">{error}</FieldDescription>}
          <Field>
            <Button type="submit" disabled={loading}>
              {loading ? 'Signing in...' : 'Login'}
            </Button>
          </Field>
          <FieldSeparator>Or</FieldSeparator>
          <Field>
            <Button variant="outline" type="button" onClick={handleGitHubSignIn}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                <path
                  d="M12 0C5.37 0 0 5.37 0 12c0 5.302 3.438 9.8 8.207 11.387.6.11.82-.26.82-.577v-2.165c-3.338.726-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.757-1.333-1.757-1.089-.745.083-.729.083-.729 1.205.084 1.84 1.237 1.84 1.237 1.07 1.834 2.807 1.304 3.492.997.108-.775.418-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.468-2.381 1.235-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.3 1.23A11.51 11.51 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.29-1.552 3.297-1.23 3.297-1.23.653 1.652.242 2.873.118 3.176.77.84 1.235 1.91 1.235 3.221 0 4.61-2.807 5.625-5.48 5.921.43.372.823 1.102.823 2.222v3.293c0 .32.218.694.825.576C20.565 21.796 24 17.3 24 12c0-6.63-5.37-12-12-12z"
                  fill="currentColor"
                />
              </svg>
              Continue with GitHub
            </Button>
          </Field>
        </FieldGroup>
      </form>
      <FieldDescription className="px-6 text-center">
        By clicking continue, you agree to our{' '}
        <a href={appPaths.legal.terms.href}>Terms of Service</a> and{' '}
        <a href={appPaths.legal.privacy.href}>Privacy Policy</a>.
      </FieldDescription>
    </div>
  )
}
