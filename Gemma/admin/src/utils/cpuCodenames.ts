/**
 * Intel CPU Codename Mapping
 * Maps CPU model numbers to Intel architecture codenames
 */

interface CodenameMapping {
  pattern: RegExp;
  codename: string;
}

// Intel codename mappings (newest to oldest)
const INTEL_CODENAMES: CodenameMapping[] = [
  // Arrow Lake (15th Gen, 2024)
  { pattern: /Core Ultra [579] 2\d{2}[A-Z]*/i, codename: 'Arrow Lake' },
  { pattern: /i[3579]-15\d{2,3}/i, codename: 'Arrow Lake' },

  // Raptor Lake Refresh (14th Gen, 2023)
  { pattern: /i[3579]-14\d{2,3}/i, codename: 'Raptor Lake' },

  // Raptor Lake (13th Gen, 2022)
  { pattern: /i[3579]-13\d{2,3}/i, codename: 'Raptor Lake' },

  // Alder Lake (12th Gen, 2021)
  { pattern: /i[3579]-12\d{2,3}/i, codename: 'Alder Lake' },

  // Rocket Lake (11th Gen Desktop, 2021)
  { pattern: /i[3579]-11\d{2,3}[A-Z]*/i, codename: 'Rocket Lake' },

  // Tiger Lake (11th Gen Mobile, 2020)
  { pattern: /i[3579]-11\d{2}G\d/i, codename: 'Tiger Lake' },

  // Comet Lake (10th Gen, 2020)
  { pattern: /i[3579]-10\d{2,3}/i, codename: 'Comet Lake' },

  // Ice Lake (10th Gen Mobile, 2019)
  { pattern: /i[3579]-10\d{2}G\d/i, codename: 'Ice Lake' },

  // Coffee Lake Refresh (9th Gen, 2018)
  { pattern: /i[3579]-9\d{2,3}/i, codename: 'Coffee Lake' },

  // Coffee Lake (8th Gen, 2017)
  { pattern: /i[3579]-8\d{2,3}/i, codename: 'Coffee Lake' },

  // Kaby Lake (7th Gen, 2016)
  { pattern: /i[3579]-7\d{2,3}/i, codename: 'Kaby Lake' },

  // Skylake (6th Gen, 2015)
  { pattern: /i[3579]-6\d{2,3}/i, codename: 'Skylake' },

  // Core Ultra (Meteor Lake, 2023)
  { pattern: /Core Ultra [579] 1\d{2}[A-Z]*/i, codename: 'Meteor Lake' },
];

// AMD codename mappings
const AMD_CODENAMES: CodenameMapping[] = [
  // Ryzen 9000 series (Granite Ridge, 2024)
  { pattern: /Ryzen [3579] 9\d{3}/i, codename: 'Granite Ridge' },

  // Ryzen 7000 series (Raphael, 2022)
  { pattern: /Ryzen [3579] 7\d{3}/i, codename: 'Raphael' },

  // Ryzen 5000 series (Vermeer, 2020)
  { pattern: /Ryzen [3579] 5\d{3}/i, codename: 'Vermeer' },

  // Ryzen 3000 series (Matisse, 2019)
  { pattern: /Ryzen [3579] 3\d{3}/i, codename: 'Matisse' },
];

/**
 * Get CPU codename from brand string
 * @param brandString Full CPU brand string (e.g., "Intel Core i5-14600KF")
 * @returns Object with codename and short name
 */
export function getCpuCodename(brandString: string): { codename: string; shortName: string } {
  if (!brandString) {
    return { codename: 'Unknown', shortName: 'Unknown' };
  }

  // Try Intel mappings
  for (const mapping of INTEL_CODENAMES) {
    if (mapping.pattern.test(brandString)) {
      // Extract short model name
      const modelMatch = brandString.match(/i[3579]-\d{4,5}[A-Z]*/i) ||
                         brandString.match(/Ultra [3579] \d{3}[A-Z]*/i);
      const shortName = modelMatch ? modelMatch[0] : brandString.split(' ').slice(-1)[0];
      return { codename: mapping.codename, shortName };
    }
  }

  // Try AMD mappings
  for (const mapping of AMD_CODENAMES) {
    if (mapping.pattern.test(brandString)) {
      const modelMatch = brandString.match(/Ryzen [3579] \d{4}[A-Z]*/i);
      const shortName = modelMatch ? modelMatch[0] : brandString.split(' ').slice(-1)[0];
      return { codename: mapping.codename, shortName };
    }
  }

  // Fallback: extract last significant part
  const parts = brandString.split(' ').filter(p => p.length > 2);
  const shortName = parts.length > 0 ? parts[parts.length - 1] : brandString;

  return { codename: 'Unknown', shortName };
}

/**
 * Format CPU display string with codename
 * @param brandString Full CPU brand string
 * @returns Formatted string like "Raptor Lake - 14600KF"
 */
export function formatCpuDisplay(brandString: string): string {
  const { codename, shortName } = getCpuCodename(brandString);
  if (codename === 'Unknown') {
    return brandString;
  }
  return `${codename} - ${shortName}`;
}

/**
 * Format GPU display string (clean up verbose names)
 * @param gpuName Full GPU name
 * @returns Cleaned GPU name
 */
export function formatGpuDisplay(gpuName: string): string {
  if (!gpuName) return 'Unknown GPU';

  // Clean up NVIDIA names
  let cleaned = gpuName
    .replace(/NVIDIA /gi, '')
    .replace(/GeForce /gi, '')
    .replace(/Graphics/gi, '')
    .trim();

  return cleaned || gpuName;
}

/**
 * Format RAM display
 * @param ramGb RAM in GB
 * @returns Formatted string like "32GB"
 */
export function formatRamDisplay(ramGb: number): string {
  if (!ramGb || ramGb <= 0) return 'Unknown';
  return `${ramGb}GB`;
}
