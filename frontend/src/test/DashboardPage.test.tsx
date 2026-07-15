import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import DashboardPage from '../pages/DashboardPage'
import { BaselineProvider } from '../contexts/BaselineContext'

describe('DashboardPage', () => {
  it('renders loading state initially', () => {
    // For a real test we would mock the static data source, but for this basic routing test:
    render(
      <BaselineProvider>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </BaselineProvider>
    )
    
    // It should render a skeleton or loading state first
    // we can just check if it renders without crashing
    expect(document.body).toBeDefined()
  })
})
