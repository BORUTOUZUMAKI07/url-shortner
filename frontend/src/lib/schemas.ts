"use client"

import { z } from "zod"

export const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
})

export const createUrlSchema = z.object({
  original_url: z.string().url("Must be a valid URL"),
  workspace_id: z.number().min(1, "Please select a workspace"),
  custom_alias: z.string().min(3, "Alias must be at least 3 characters").regex(/^[a-zA-Z0-9_-]+$/, "Only letters, numbers, hyphens, underscores").optional().or(z.literal("")),
  folder_id: z.number().optional(),
  password: z.string().optional().or(z.literal("")),
  expires_at: z.string().optional().or(z.literal("")),
  is_one_time: z.boolean().optional(),
  is_ab_test: z.boolean().optional(),
  ios_url: z.string().optional().or(z.literal("")),
  android_url: z.string().optional().or(z.literal("")),
  tags: z.array(z.string()).optional(),
})

export const registerSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirmPassword: z.string().min(1, "Please confirm your password"),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
})

export type LoginFormData = z.infer<typeof loginSchema>
export type RegisterFormData = z.infer<typeof registerSchema>
export type CreateUrlFormData = z.infer<typeof createUrlSchema>
