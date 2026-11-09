/* eslint-disable @typescript-eslint/no-unused-vars -- type parameters must match the declaration being merged */
import 'chart.js'

declare module 'chart.js' {
  // our own dataset flag: leave this series out of the tooltip (range bands, floor line)
  interface ChartDatasetProperties<TType extends ChartType, TData> {
    hideTip?: boolean
  }
}
