import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

/** Supabase client for authentication only; data access goes through the PharmaLens API. Null if unconfigured. */
export const supabase: SupabaseClient | null = url && anonKey ? createClient(url, anonKey) : null
