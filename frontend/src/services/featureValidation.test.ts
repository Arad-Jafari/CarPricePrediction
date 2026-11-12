import { describe, expect, it } from 'vitest'
import { createPredictionSchema } from './featureValidation'
import type { Feature } from '../types'

const features: Feature[] = [
  { name: 'year', display_label: 'Vehicle year', type: 'integer', required: true, minimum: 1380, maximum: 1402 },
  { name: 'mileage', display_label: 'Mileage', type: 'integer', required: true, minimum: 0, maximum: 900000 },
  { name: 'trim', type: 'string', required: true, supported_values: ['تیپ 2', 'تیپ 5'] },
  { name: 'transmission', type: 'string', required: true, supported_values: ['دنده ای'] },
  { name: 'body_status', type: 'string', required: true, supported_values: ['بدون رنگ'] },
  { name: 'color', type: 'string', required: true, supported_values: ['سفید', 'دلفینی'] },
]

describe('dynamic model input validation', () => {
  const schema = createPredictionSchema(features)
  const supportedInput = {
    year: 1398,
    mileage: 95000,
    trim: 'تیپ 2',
    transmission: 'دنده ای',
    body_status: 'بدون رنگ',
    color: 'سفید',
  }

  it('accepts a supported training-compatible input', () => {
    expect(schema.safeParse(supportedInput).success).toBe(true)
  })

  it('rejects unsupported categories, missing values, and out-of-domain numbers', () => {
    expect(schema.safeParse({ ...supportedInput, trim: 'unsupported' }).success).toBe(false)
    expect(schema.safeParse({ ...supportedInput, mileage: 900001 }).success).toBe(false)
    const { color: _color, ...missingColor } = supportedInput
    expect(schema.safeParse(missingColor).success).toBe(false)
  })

  it('rejects attributes not included in the model contract', () => {
    expect(schema.safeParse({ ...supportedInput, model: '206' }).success).toBe(false)
  })
})
