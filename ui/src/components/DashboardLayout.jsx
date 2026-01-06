import { useState, useEffect, useMemo } from 'react';
import Chart from './Chart';

const TOTAL_BLOCKS = 60;
const MAX_BLOCK_PX = 30;
const MIN_BLOCK_PX = 20;
const BLOCK_HEIGHT_PX = 30;

function useBlockSize() {
  const [containerWidth, setContainerWidth] = useState(
    typeof window !== 'undefined' ? window.innerWidth : 1800
  );

  useEffect(() => {
    function handleResize() {
      setContainerWidth(window.innerWidth);
    }
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const blockPx = useMemo(() => {
    const rawBlockPx = containerWidth / TOTAL_BLOCKS;
    if (rawBlockPx >= MAX_BLOCK_PX) {
      return MAX_BLOCK_PX;
    }
    if (rawBlockPx <= MIN_BLOCK_PX) {
      return MIN_BLOCK_PX;
    }
    return rawBlockPx;
  }, [containerWidth]);

  const blocksPerRow = useMemo(() => {
    if (blockPx >= MAX_BLOCK_PX) {
      return TOTAL_BLOCKS;
    }
    return Math.floor(containerWidth / blockPx);
  }, [containerWidth, blockPx]);

  return { blockPx, blocksPerRow };
}

export default function DashboardLayout({ layout, chartsMap, globalZoomCommand = null }) {
  const { blockPx, blocksPerRow } = useBlockSize();

  const rows = useMemo(() => {
    const result = [];
    let currentRow = [];
    let currentRowBlocks = 0;

    for (const item of layout) {
      const effectiveWidth = Math.min(item.width, blocksPerRow);

      if (currentRowBlocks + effectiveWidth > blocksPerRow) {
        if (currentRow.length > 0) {
          result.push(currentRow);
        }
        currentRow = [{ ...item, effectiveWidth }];
        currentRowBlocks = effectiveWidth;
      } else {
        currentRow.push({ ...item, effectiveWidth });
        currentRowBlocks += effectiveWidth;
      }
    }

    if (currentRow.length > 0) {
      result.push(currentRow);
    }

    return result;
  }, [layout, blocksPerRow]);

  const totalWidthPx = blocksPerRow * blockPx;

  return (
    <div
      className="dashboard-layout"
      style={{
        width: totalWidthPx,
        maxWidth: '100%',
        margin: '0 auto',
      }}
    >
      {rows.map((row, rowIdx) => (
        <div
          key={rowIdx}
          className="dashboard-row"
          style={{
            display: 'flex',
            flexWrap: 'nowrap',
          }}
        >
          {row.map((item, itemIdx) => {
            const widthPx = item.effectiveWidth * blockPx;
            const heightPx = item.height * BLOCK_HEIGHT_PX;
            const chart = chartsMap[item.chartId];

            return (
              <div
                key={item.chartId || itemIdx}
                className="dashboard-cell"
                style={{
                  width: widthPx,
                  height: heightPx,
                  boxSizing: 'border-box',
                  overflow: 'hidden',
                }}
              >
                {chart ? (
                  <Chart
                    chart={chart}
                    onUpdate={() => {}}
                    onDelete={() => {}}
                    fillParent
                    globalZoomCommand={globalZoomCommand}
                    interpolateToLatestOverride={
                      typeof item.interpolateToLatest === 'boolean'
                        ? item.interpolateToLatest
                        : undefined
                    }
                  />
                ) : (
                  <div
                    style={{
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: '#f5f5f5',
                      border: '1px dashed #ccc',
                    }}
                  >
                    Chart not found: {item.chartId}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
