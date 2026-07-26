const viewerOrigin = window.location.origin;

window.config = {
  routerBasename: '/',
  showStudyList: true,
  extensions: [],
  modes: [],
  dataSources: [
    {
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'orthanc',
      configuration: {
        friendlyName: 'Local Orthanc',
        name: 'orthanc',
        qidoRoot: `${viewerOrigin}/dicom-web`,
        wadoRoot: `${viewerOrigin}/dicom-web`,
        wadoUriRoot: `${viewerOrigin}/wado`,
        qidoSupportsIncludeField: true,
        supportsFuzzyMatching: false,
        supportsWildcard: true,
        staticWado: false,
        singlepart: 'bulkdata',
        imageRendering: 'wadors',
        thumbnailRendering: 'wadors',
        enableStudyLazyLoad: true,
        queryLimit: 101
      }
    }
  ],
  defaultDataSourceName: 'orthanc'
};
