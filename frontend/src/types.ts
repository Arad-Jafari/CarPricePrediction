export type User = {
  id: string
  full_name: string
  email: string
}

export type CarInput = {
  year: number
  mileage: number
  trim: string
  transmission: string
  body_status: string
  color: string
}

export type Prediction = {
  id: string
  input_data: CarInput
  predicted_price: number
  prediction_unit: string
  model_version: string
  created_at: string
}

export type Feature = {
  name: keyof CarInput
  display_label?: string
  type: 'integer' | 'string'
  required: boolean
  minimum?: number
  maximum?: number
  unit?: string | null
  supported_values?: string[]
  constraint_note?: string
}
