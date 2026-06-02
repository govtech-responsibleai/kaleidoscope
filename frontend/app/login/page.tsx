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
} from "@mui/material";
import { useRouter } from "next/navigation";
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";
import axios from "axios";
import { authApi } from "@/lib/api";
import Image from "next/image";

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

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await authApi.login(username, password);
      router.push("/");
    } catch {
      setError("Invalid username or password");
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
            Sign in to continue
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
              label="Username"
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
            <Button
              fullWidth
              variant="contained"
              type="submit"
              disabled={loading}
              sx={{ mt: 3 }}
            >
              {loading ? <CircularProgress size={24} /> : "Sign In"}
            </Button>
          </form>

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
