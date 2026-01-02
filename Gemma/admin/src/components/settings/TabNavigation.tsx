/**
 * TabNavigation - Tab bar for admin panel
 */

import type { AdminTab, TabDefinition } from '../../types/admin';
import {
  Server,
  Cpu,
  Radar,
  Gamepad2,
  Zap,
  Cloud,
  User,
} from 'lucide-react';

const TAB_DEFINITIONS: TabDefinition[] = [
  { id: 'services', label: 'Services', description: 'Service configuration and status' },
  { id: 'omniparser', label: 'OmniParser', description: 'Vision AI server settings' },
  { id: 'discovery', label: 'Discovery', description: 'SUT discovery settings' },
  { id: 'games', label: 'Games', description: 'Game YAML editor' },
  { id: 'automation', label: 'Automation', description: 'Automation timing and behavior' },
  { id: 'steam', label: 'Steam', description: 'Steam account management' },
  { id: 'profiles', label: 'Profiles', description: 'Environment profiles' },
];

const TAB_ICONS: Record<AdminTab, React.ReactNode> = {
  services: <Server className="w-4 h-4" />,
  omniparser: <Cpu className="w-4 h-4" />,
  discovery: <Radar className="w-4 h-4" />,
  games: <Gamepad2 className="w-4 h-4" />,
  automation: <Zap className="w-4 h-4" />,
  steam: <Cloud className="w-4 h-4" />,
  profiles: <User className="w-4 h-4" />,
};

interface TabNavigationProps {
  activeTab: AdminTab;
  onTabChange: (tab: AdminTab) => void;
  unsavedTabs?: Set<AdminTab>;
}

export function TabNavigation({ activeTab, onTabChange, unsavedTabs = new Set() }: TabNavigationProps) {
  return (
    <div className="bg-surface-elevated border-b border-border">
      <div className="flex items-center gap-1 px-4 py-2 overflow-x-auto">
        {TAB_DEFINITIONS.map(tab => {
          const isActive = activeTab === tab.id;
          const hasUnsaved = unsavedTabs.has(tab.id);

          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`
                flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg
                transition-all whitespace-nowrap relative
                ${isActive
                  ? 'bg-primary text-white shadow-md'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
                }
              `}
              title={tab.description}
            >
              {TAB_ICONS[tab.id]}
              <span>{tab.label}</span>
              {hasUnsaved && (
                <span
                  className={`
                    absolute -top-1 -right-1 w-2 h-2 rounded-full
                    ${isActive ? 'bg-warning' : 'bg-warning'}
                  `}
                  title="Unsaved changes"
                />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default TabNavigation;
