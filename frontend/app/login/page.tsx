"use client";

import React, { useState, useEffect } from "react";
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Stack,
  Divider,
  Link,
} from "@mui/material";
import { useRouter } from "next/navigation";
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";
import axios from "axios";
import { authApi } from "@/lib/api";
import Image from "next/image";

type AuthMode = "signin" | "signup";

export default function LoginPage() {
  const router = useRouter();
  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    const expired = sessionStorage.getItem("session_expired") === "true";
    if (expired) {
      sessionStorage.removeItem("session_expired");
      setSessionExpired(true);
    }
  }, []);

  const [mode, setMode] = useState<AuthMode>("signin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const switchMode = (next: AuthMode) => {
    setMode(next);
    setError("");
    setPassword("");
    setConfirmPassword("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (mode === "signup" && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      if (mode === "signin") {
        await authApi.login(username, password);
      } else {
        await authApi.signup(username, password);
      }
      router.push("/");
    } catch (err) {
      if (mode === "signin") {
        setError("Invalid username or password");
      } else if (axios.isAxiosError(err) && err.response?.status === 403) {
        setError("This email has not been invited to sign up. Please contact the organiser.");
      } else if (axios.isAxiosError(err) && err.response?.status === 400) {
        setError("An account with this email already exists. Try signing in instead.");
      } else {
        setError("Unable to create your account. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (credential?: string) => {
    setError("");
    if (!credential) {
      setError("Unable to sign in with Google. Please try again.");
      return;
    }
    setLoading(true);

    try {
      await authApi.googleLogin(credential);
      router.push("/");
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 403) {
        setError("Access is restricted to authorised email domains. Please sign in with your work account.");
      } else {
        setError("Unable to sign in with Google. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const isSignup = mode === "signup";

  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="100vh"
      bgcolor="rgb(0,0,0,0.05)"
    >
      <Card sx={{ width: 400, p: 2 }}>
        <CardContent >
          <Stack direction="row" justifyContent="center" alignItems="center" sx={{ gap: 1.5, mb: 1  }}>
            <Image src="/icon.png" alt="Kaleidoscope Logo" width={28} height={28} unoptimized />
            <Typography variant="h5" component="h1" textAlign="center">
              Kaleidoscope
            </Typography>
          </Stack>
          <Typography variant="body2" color="text.secondary" textAlign="center" mb={3}>
            {isSignup ? "Create an account to continue" : "Sign in to continue"}
          </Typography>

          {sessionExpired && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Your session has expired. Please sign in again.
            </Alert>
          )}

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label={isSignup ? "Email" : "Username"}
              type={isSignup ? "email" : "text"}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              margin="normal"
              required
              autoFocus
            />
            <TextField
              fullWidth
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              margin="normal"
              required
            />
            {isSignup && (
              <TextField
                fullWidth
                label="Confirm password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                margin="normal"
                required
              />
            )}
            <Button
              fullWidth
              variant="contained"
              type="submit"
              disabled={loading}
              sx={{ mt: 3 }}
            >
              {loading ? <CircularProgress size={24} /> : isSignup ? "Sign Up" : "Sign In"}
            </Button>
          </form>

          <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ mt: 2 }}>
            {isSignup ? (
              <>
                Already have an account?{" "}
                <Link component="button" type="button" onClick={() => switchMode("signin")}>
                  Sign in
                </Link>
              </>
            ) : (
              <>
                Been invited?{" "}
                <Link component="button" type="button" onClick={() => switchMode("signup")}>
                  Sign up
                </Link>
              </>
            )}
          </Typography>

          {googleClientId && (
            <>
              <Divider sx={{ my: 3 }}>or</Divider>
              <GoogleOAuthProvider clientId={googleClientId}>
                <Box display="flex" justifyContent="center">
                  <GoogleLogin
                    onSuccess={(credentialResponse) => handleGoogleSuccess(credentialResponse.credential)}
                    onError={() => setError("Unable to sign in with Google. Please try again.")}
                  />
                </Box>
              </GoogleOAuthProvider>
            </>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
