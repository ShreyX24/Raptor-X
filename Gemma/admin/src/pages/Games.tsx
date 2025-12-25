import { useState } from 'react';
import { useGames, useDevices } from '../hooks';
import { GameCard } from '../components';
import { startRun } from '../api';
import type { GameConfig } from '../types';

export function Games() {
  const { gamesList, loading, reload } = useGames();
  const { onlineDevices } = useDevices();
  const [reloading, setReloading] = useState(false);
  const [selectedGame, setSelectedGame] = useState<GameConfig | null>(null);
  const [showRunModal, setShowRunModal] = useState(false);

  const handleReload = async () => {
    setReloading(true);
    try {
      await reload();
    } catch (error) {
      console.error('Reload failed:', error);
    } finally {
      setReloading(false);
    }
  };

  const handleRunGame = (gameName: string) => {
    const game = gamesList.find(g => g.name === gameName);
    if (game) {
      setSelectedGame(game);
      setShowRunModal(true);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Games</h1>
          <p className="text-gray-500">Configure and run game automation</p>
        </div>
        <button
          onClick={handleReload}
          disabled={reloading}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 disabled:bg-gray-50"
        >
          {reloading ? 'Reloading...' : 'Reload Configs'}
        </button>
      </div>

      {/* Game Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-2/3 mb-4"></div>
              <div className="h-3 bg-gray-200 rounded w-1/2 mb-2"></div>
              <div className="h-3 bg-gray-200 rounded w-1/3"></div>
            </div>
          ))}
        </div>
      ) : gamesList.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <p className="text-gray-500">No games configured</p>
          <p className="text-sm text-gray-400 mt-2">
            Add game configurations to the config directory
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {gamesList.map((game) => (
            <GameCard
              key={game.name}
              game={game}
              onSelect={setSelectedGame}
              onRun={handleRunGame}
              isSelected={selectedGame?.name === game.name}
              disabled={onlineDevices.length === 0}
            />
          ))}
        </div>
      )}

      {/* Run Modal */}
      {showRunModal && selectedGame && (
        <RunGameModal
          game={selectedGame}
          devices={onlineDevices}
          onClose={() => {
            setShowRunModal(false);
            setSelectedGame(null);
          }}
        />
      )}
    </div>
  );
}

interface RunGameModalProps {
  game: GameConfig;
  devices: Array<{ device_id: string; ip: string; hostname: string }>;
  onClose: () => void;
}

function RunGameModal({ game, devices, onClose }: RunGameModalProps) {
  const [selectedDevice, setSelectedDevice] = useState('');
  const [iterations, setIterations] = useState(1);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStart = async () => {
    if (!selectedDevice) return;

    setStarting(true);
    setError(null);

    try {
      await startRun(selectedDevice, game.name, iterations);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start run');
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h2 className="text-xl font-bold text-gray-900 mb-4">
          Run {game.display_name || game.name}
        </h2>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Select SUT
            </label>
            <select
              value={selectedDevice}
              onChange={(e) => setSelectedDevice(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2"
            >
              <option value="">Choose a device...</option>
              {devices.map((device) => (
                <option key={device.device_id} value={device.ip}>
                  {device.hostname || device.ip}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Iterations
            </label>
            <input
              type="number"
              min="1"
              max="100"
              value={iterations}
              onChange={(e) => setIterations(parseInt(e.target.value) || 1)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2"
            />
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 font-medium hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleStart}
            disabled={!selectedDevice || starting}
            className="flex-1 px-4 py-2 bg-green-500 text-white rounded-lg font-medium hover:bg-green-600 disabled:bg-gray-300"
          >
            {starting ? 'Starting...' : 'Start'}
          </button>
        </div>
      </div>
    </div>
  );
}
