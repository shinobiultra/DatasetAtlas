import { describe, expect, it } from 'vitest'
import { legendPlan } from './bulk'

const categories = (counts: number[]) => counts.map(count => ({ count }))

describe('legend for a field column', () => {
  it('names every category when they all fit, and keeps the server’s other bucket apart', () => {
    expect(legendPlan(categories([5, 4, 3]), 0, 14)).toEqual({ named: 3, rest: 0 })
    expect(legendPlan(categories([5, 4, 3]), 7, 14)).toEqual({ named: 3, rest: 7 })
  })

  it('leaves room for the other entry when there are exactly as many categories as the legend holds', () => {
    const fourteen = categories(Array.from({ length: 14 }, () => 10))
    expect(legendPlan(fourteen, 0, 14)).toEqual({ named: 14, rest: 0 })
    expect(legendPlan(fourteen, 5, 14)).toEqual({ named: 13, rest: 15 })
  })

  it('folds the tail into other so legend counts add up to every point with a value', () => {
    const many = categories([100, 90, 80, 70, 60, 50])
    const { named, rest } = legendPlan(many, 25, 4)
    expect(named).toBe(3)
    expect(many.slice(0, named).reduce((total, category) => total + category.count, 0) + rest).toBe(475)
  })
})
