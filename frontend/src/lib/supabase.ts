import { createClient } from '@supabase/supabase-js';

const supabaseUrl =
  import.meta.env.VITE_SUPABASE_URL || 'https://demo.supabase.co';

// Support both standard VITE_SUPABASE_ANON_KEY and Supabase's new publishable key (VITE_SUPABASE_PUBLISHABLE_KEY)
const supabaseKey =
  (import.meta.env.VITE_SUPABASE_ANON_KEY && import.meta.env.VITE_SUPABASE_ANON_KEY !== 'demo-anon-key')
    ? import.meta.env.VITE_SUPABASE_ANON_KEY
    : (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || import.meta.env.VITE_SUPABASE_ANON_KEY || 'demo-anon-key');

export const isSupabaseConfigured =
  Boolean(supabaseUrl) &&
  !supabaseUrl.includes('demo.supabase.co') &&
  Boolean(supabaseKey) &&
  supabaseKey !== 'demo-anon-key';

export const getSupabaseConfig = () => ({
  url: supabaseUrl,
  configured: isSupabaseConfigured,
  projectRef: supabaseUrl.replace(/^https?:\/\//, '').split('.')[0] || '',
});

export const supabase = createClient(supabaseUrl, supabaseKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
});

/**
 * Perform a live check against the configured Supabase endpoint
 */
export const checkSupabaseConnection = async (): Promise<{
  connected: boolean;
  message: string;
}> => {
  if (!isSupabaseConfigured) {
    return {
      connected: false,
      message: 'Supabase URL or Key is not configured (using local mock/demo)',
    };
  }

  try {
    const { error } = await supabase.auth.getSession();
    if (error) {
      return {
        connected: false,
        message: error.message,
      };
    }
    return {
      connected: true,
      message: 'Supabase connected and authenticated successfully',
    };
  } catch (err: any) {
    return {
      connected: false,
      message: err?.message || 'Network connection error to Supabase',
    };
  }
};

