import { useState } from 'react';
import { useSystemStatus, useDevices, useGames, useRuns } from '../hooks';
import { ServiceStatus, SUTCard, GameCard, RunCard } from '../components';
import type { SUT, GameConfig } from '../types';

export function Dashboard() {
  const { status } = useSystemStatus();
  const { devices, pair, unpair } = useDevices();
  const { gamesList } = useGames();
  const { activeRunsList, start, stop } = useRuns();

  const [selectedSut, setSelectedSut] = useState<SUT | null>(null);
  const [selectedGame, setSelectedGame] = useState<GameConfig | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onlineDevices = devices.filter(d => d.status === 'online');

  const handleStartRun = async () => {
    if (!selectedSut || !selectedGame) return;

    setIsStarting(true);
    setError(null);

    try {
      await start(selectedSut.ip, selectedGame.name, 1);
      setSelectedSut(null);
      setSelectedGame(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start run');
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500">Monitor and control your game automation</p>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-4 text-red-500 hover:text-red-700"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column - Status & Quick Actions */}
        <div className="space-y-6">
          <ServiceStatus systemStatus={status} />

          {/* Quick Start */}
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="font-semibold text-gray-900 mb-4">Quick Start</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 mb-2">
                  Selected SUT
                </label>
                <div className="p-3 bg-gray-50 rounded-lg text-sm">
                  {selectedSut ? (
                    <div className="flex items-center justify-between">
                      <span>{selectedSut.hostname || selectedSut.ip}</span>
                      <button
                        onClick={() => setSelectedSut(null)}
                        className="text-gray-400 hover:text-gray-600"
                      >
                        Clear
                      </button>
                    </div>
                  ) : (
                    <span className="text-gray-400">Select a SUT from below</span>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-2">
                  Selected Game
                </label>
                <div className="p-3 bg-gray-50 rounded-lg text-sm">
                  {selectedGame ? (
                    <div className="flex items-center justify-between">
                      <span>{selectedGame.display_name || selectedGame.name}</span>
                      <button
                        onClick={() => setSelectedGame(null)}
                        className="text-gray-400 hover:text-gray-600"
                      >
                        Clear
                      </button>
                    </div>
                  ) : (
                    <span className="text-gray-400">Select a game from below</span>
                  )}
                </div>
              </div>

              <button
                onClick={handleStartRun}
                disabled={!selectedSut || !selectedGame || isStarting}
                className="w-full py-2 rounded-lg bg-green-500 text-white font-medium hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                {isStarting ? 'Starting...' : 'Start Automation'}
              </button>
            </div>
          </div>
        </div>

        {/* Middle Column - Online SUTs */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">
              Online SUTs ({onlineDevices.length})
            </h3>
          </div>

          <div className="space-y-4 max-h-[600px] overflow-y-auto">
            {onlineDevices.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No online SUTs found
              </div>
            ) : (
              onlineDevices.map((sut) => (
                <SUTCard
                  key={sut.device_id}
                  sut={sut}
                  onSelect={setSelectedSut}
                  onPair={(id) => pair(id).catch(console.error)}
                  onUnpair={(id) => unpair(id).catch(console.error)}
                  isSelected={selectedSut?.device_id === sut.device_id}
                />
              ))
            )}
          </div>
        </div>

        {/* Right Column - Games & Active Runs */}
        <div className="space-y-6">
          {/* Games */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">
                Games ({gamesList.length})
              </h3>
            </div>

            <div className="space-y-4 max-h-[300px] overflow-y-auto">
              {gamesList.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  No games configured
                </div>
              ) : (
                gamesList.slice(0, 4).map((game) => (
                  <GameCard
                    key={game.name}
                    game={game}
                    onSelect={setSelectedGame}
                    isSelected={selectedGame?.name === game.name}
                    disabled={!selectedSut}
                  />
                ))
              )}
            </div>
          </div>

          {/* Active Runs */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">
                Active Runs ({activeRunsList.length})
              </h3>
            </div>

            <div className="space-y-4">
              {activeRunsList.length === 0 ? (
                <div className="text-center py-8 text-gray-500 bg-white rounded-lg border border-gray-200">
                  No active runs
                </div>
              ) : (
                activeRunsList.map((run) => (
                  <RunCard
                    key={run.run_id}
                    run={run}
                    onStop={(id) => stop(id).catch(console.error)}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
