import { useEffect, useState } from 'react';
import { DEPARTMENTS, DIVISIONS, UNITS } from '../types';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

export interface OrgTree {
  divisions: string[];
  departments: Record<string, string[]>;
  units: Record<string, string[]>;
}

function fallbackTree(): OrgTree {
  return {
    divisions: [...DIVISIONS],
    departments: DEPARTMENTS,
    units: UNITS,
  };
}

export function useOrgTree(): OrgTree {
  const [tree, setTree] = useState<OrgTree>(fallbackTree);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/org`)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('org tree unavailable'))))
      .then((data: { divisions?: { division: string; departments?: { department: string; units?: string[] }[] }[] }) => {
        if (cancelled) return;
        const divisions: string[] = [];
        const departments: Record<string, string[]> = {};
        const units: Record<string, string[]> = {};
        for (const division of data.divisions ?? []) {
          divisions.push(division.division);
          departments[division.division] = (division.departments ?? []).map((item) => item.department);
          for (const item of division.departments ?? []) {
            units[item.department] = item.units ?? [];
          }
        }
        if (divisions.length) setTree({ divisions, departments, units });
      })
      .catch(() => {
        // Keep the static fallback when the API is down.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return tree;
}
