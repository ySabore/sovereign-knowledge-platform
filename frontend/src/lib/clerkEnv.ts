/** True when Vite was built with a Clerk publishable key (optional auth provider). */
export const clerkEnabled = Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY?.trim());
