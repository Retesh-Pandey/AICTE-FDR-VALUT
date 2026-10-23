import React, { createContext, useContext, useEffect, useState } from 'react';
import { api, setAuthToken, User } from '@/lib/api';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';

interface AuthContextType {
  user: User | null;
  role: 'institution' | 'officer' | 'admin' | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isSupabaseActive: boolean;
  login: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, metadata?: { full_name?: string; role?: string }) => Promise<{ needsEmailConfirmation: boolean }>;
  loginWithDemo: (email: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = async () => {
    try {
      const data = await api.getMe();
      setUser(data);
    } catch {
      setUser(null);
      setAuthToken(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem('vault_token');
    if (token) {
      setAuthToken(token);
      refreshUser();
    } else {
      setIsLoading(false);
    }

    // Subscribe to Supabase Auth state changes if Supabase is configured
    if (isSupabaseConfigured) {
      const {
        data: { subscription },
      } = supabase.auth.onAuthStateChange(async (event, session) => {
        if (event === 'SIGNED_IN' && session?.access_token) {
          setAuthToken(session.access_token);
          refreshUser();
        } else if (event === 'SIGNED_OUT') {
          setAuthToken(null);
          setUser(null);
        }
      });

      return () => {
        subscription.unsubscribe();
      };
    }
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      // If Supabase is configured, attempt Supabase Auth first
      if (isSupabaseConfigured) {
        try {
          const { data, error } = await supabase.auth.signInWithPassword({
            email,
            password,
          });
          if (!error && data.session?.access_token) {
            setAuthToken(data.session.access_token);
            try {
              const profile = await api.getMe();
              setUser(profile);
              return;
            } catch {
              // If backend profile sync doesn't match yet, fall through to backend login
            }
          }
        } catch {
          // Fall through to backend API login
        }
      }

      const res = await api.login(email, password);
      setAuthToken(res.access_token);
      setUser(res.user);
    } catch (err) {
      console.error('Login failed:', err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const signUp = async (
    email: string,
    password: string,
    metadata?: { full_name?: string; role?: string }
  ): Promise<{ needsEmailConfirmation: boolean }> => {
    setIsLoading(true);
    try {
      if (!isSupabaseConfigured) {
        throw new Error('Supabase Auth is not configured. Please check your environment variables.');
      }
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            full_name: metadata?.full_name || '',
            role: metadata?.role || 'institution',
          },
        },
      });
      if (error) {
        throw error;
      }
      if (data.session?.access_token) {
        setAuthToken(data.session.access_token);
        await refreshUser();
        return { needsEmailConfirmation: false };
      }
      return { needsEmailConfirmation: true };
    } catch (err) {
      console.error('Sign up failed:', err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const loginWithDemo = async (email: string) => {
    setIsLoading(true);
    try {
      const res = await api.demoLogin(email);
      setAuthToken(res.access_token);
      setUser(res.user);
    } catch (err) {
      console.error('Demo login failed:', err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    if (isSupabaseConfigured) {
      supabase.auth.signOut().catch(() => {});
    }
    setAuthToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        role: user?.role || null,
        isAuthenticated: !!user,
        isLoading,
        isSupabaseActive: isSupabaseConfigured,
        login,
        signUp,
        loginWithDemo,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
