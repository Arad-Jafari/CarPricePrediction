import { z } from 'zod'
import type { Feature } from '../types'

export function createPredictionSchema(features: Feature[]) {
  const shape = Object.fromEntries(features.map((feature) => [
    feature.name,
    feature.type === 'integer'
      ? z.number().int().min(feature.minimum ?? Number.MIN_SAFE_INTEGER).max(feature.maximum ?? Number.MAX_SAFE_INTEGER)
      : z.string().refine(
          (value) => (feature.supported_values ?? []).includes(value),
          'Select a supported training value.'
        )
  ])) as Record<string, z.ZodType>

  return z.object(shape).strict()
}
