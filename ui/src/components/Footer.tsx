import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';

export function Footer() {
  const [apiVersion, setApiVersion] = useState<string>('loading...');
  const frontendVersion = __APP_VERSION__;

  useEffect(() => {
    let isMounted = true;

    async function fetchApiVersion() {
      const result = await apiClient.getApiVersion();
      if (isMounted) {
        setApiVersion(result.version);
      }
    }

    fetchApiVersion();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <footer className="bg-white/80 backdrop-blur-md border-t border-slate-200 py-4 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center text-sm text-slate-600 mb-2">
          Frontend Version: {frontendVersion} | API Version: {apiVersion}
        </div>
        <div className="text-center text-xs text-slate-500">
          Designed, Built and Maintained with Love by the{' '}
          <a
            href="https://github.com/orgs/letsconfab/people"
            target="_blank"
            rel="noopener noreferrer"
            className="text-violet-600 hover:text-violet-700 hover:underline"
          >
            letsconfab team
          </a>
        </div>
      </div>
    </footer>
  );
}
