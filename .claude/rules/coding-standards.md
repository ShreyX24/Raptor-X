# Coding Standards

## Python (Backend Services)

### Style
- 4-space indentation
- Type hints required for function signatures
- Docstrings for public functions (Google style)
- Max line length: 100 characters

### Imports
```python
# Standard library
import os
import sys
from typing import Optional, List, Dict

# Third-party
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Local
from .core import controller
from .api import routes
```

### Error Handling
```python
# DO: Specific exceptions with context
raise HTTPException(status_code=404, detail=f"Game '{game_name}' not found")

# DON'T: Generic exceptions
raise Exception("Error")
```

### Logging
```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Starting automation for {game_name}")
logger.error(f"Failed to connect to SUT: {e}")
```

## TypeScript/React (Frontend)

### Style
- 2-space indentation
- Use functional components with hooks
- Prefer `const` over `let`
- Use TypeScript strict mode

### Component Structure
```tsx
// Imports
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';

// Types
interface Props {
  gameId: string;
  onSelect: (game: Game) => void;
}

// Component
export function GameCard({ gameId, onSelect }: Props) {
  // Hooks first
  const [isLoading, setIsLoading] = useState(false);
  const { data: game } = useQuery(['game', gameId], fetchGame);

  // Effects
  useEffect(() => {
    // ...
  }, [gameId]);

  // Handlers
  const handleClick = () => {
    onSelect(game);
  };

  // Render
  return (
    <div onClick={handleClick}>
      {game?.name}
    </div>
  );
}
```

### API Calls
```tsx
// Use React Query for data fetching
const { data, isLoading, error } = useQuery({
  queryKey: ['runs'],
  queryFn: () => api.getRuns(),
  refetchInterval: 5000,
});
```

## Git Commits

### Format
```
<type>: <short description>

<optional body with details>

<optional footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code restructuring
- `docs`: Documentation
- `style`: Formatting
- `test`: Tests
- `chore`: Maintenance

### Examples
```
feat: Add Steam dialog detection via OmniParser

- Focus Steam window before screenshot
- Parse for update/sync dialog text
- Auto-dismiss dialogs when detected

fix: Timeline events not persisting to disk

The timeline was saving to wrong directory due to
path mismatch between run_storage and timeline_manager.
```

## API Design

### REST Endpoints
- Use plural nouns: `/api/runs`, `/api/games`
- Use HTTP methods correctly: GET (read), POST (create), PUT (update), DELETE
- Return appropriate status codes: 200, 201, 400, 404, 500

### Response Format
```json
{
  "status": "success",
  "data": { ... },
  "message": "optional message"
}
```

### Error Response
```json
{
  "status": "error",
  "error": "Error description",
  "detail": "Additional context"
}
```

## File Organization

### Backend
```
service_name/
├── src/service_name/
│   ├── __init__.py
│   ├── main.py          # Entry point
│   ├── config.py        # Configuration
│   ├── api/             # HTTP endpoints
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── health.py
│   └── core/            # Business logic
│       ├── __init__.py
│       └── manager.py
└── pyproject.toml
```

### Frontend
```
admin/
├── src/
│   ├── main.tsx         # Entry point
│   ├── App.tsx          # Root component
│   ├── api/             # API clients
│   ├── components/      # Reusable components
│   ├── hooks/           # Custom hooks
│   ├── pages/           # Page components
│   ├── types/           # TypeScript types
│   └── utils/           # Utility functions
└── package.json
```
