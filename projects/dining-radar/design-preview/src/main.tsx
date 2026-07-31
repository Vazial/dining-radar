import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import CandidateSearchPreview from './screens/CandidateSearchPreview';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <CandidateSearchPreview />
  </StrictMode>,
);
