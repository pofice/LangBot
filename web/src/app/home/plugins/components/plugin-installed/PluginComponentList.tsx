import { PluginComponent } from '@/app/infra/entities/plugin';
import { TFunction } from 'i18next';
import { Wrench, AudioWaveform, Hash } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export default function PluginComponentList({
  components,
  showComponentName,
  showTitle,
  useBadge,
  t,
}: {
  components: PluginComponent[];
  showComponentName: boolean;
  showTitle: boolean;
  useBadge: boolean;
  t: TFunction;
}) {
  const componentKindCount: Record<string, number> = {};

  for (const component of components) {
    const kind = component.manifest.manifest.kind;
    if (componentKindCount[kind]) {
      componentKindCount[kind]++;
    } else {
      componentKindCount[kind] = 1;
    }
  }

  const kindIconMap: Record<string, React.ReactNode> = {
    Tool: <Wrench className="w-5 h-5" />,
    EventListener: <AudioWaveform className="w-5 h-5" />,
    Command: <Hash className="w-5 h-5" />,
  };

  const componentKindList = Object.keys(componentKindCount);

  return (
    <>
      {showTitle && <div>{t('plugins.componentsList')}</div>}
      {componentKindList.length > 0 && (
        <>
          {componentKindList.map((kind) => {
            return (
              <>
                {useBadge && (
                  <Badge variant="outline">
                    {kindIconMap[kind]}
                    {showComponentName &&
                      t('plugins.componentName.' + kind) + '  '}
                    {componentKindCount[kind]}
                  </Badge>
                )}

                {!useBadge && (
                  <div
                    key={kind}
                    className="flex flex-row items-center justify-start gap-[0.2rem]"
                  >
                    {kindIconMap[kind]}
                    {showComponentName &&
                      t('plugins.componentName.' + kind) + '  '}
                    {componentKindCount[kind]}
                  </div>
                )}
              </>
            );
          })}
        </>
      )}

      {componentKindList.length === 0 && <div>{t('plugins.noComponents')}</div>}
    </>
  );
}
